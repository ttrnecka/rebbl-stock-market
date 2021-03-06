from sqlalchemy import or_, UniqueConstraint, desc
from .base_model import db, Base, QueryWithSoftDelete
from misc.helpers import current_round
import logging
import json
import datetime
from logging.handlers import RotatingFileHandler
import os
from decimal import Decimal


ROOT = os.path.dirname(__file__)

logger = logging.getLogger('transaction')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename=os.path.join(ROOT, '../logs/transaction.log'), encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

db_logger = logging.getLogger("DB logging")
db_logger.setLevel(logging.INFO)
handler = RotatingFileHandler(os.path.join(ROOT, '../logs/db.log'), maxBytes=10000000, backupCount=5, encoding='utf-8', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
db_logger.addHandler(handler)


class User(Base):  
    __tablename__ = 'users'
    disc_id = db.Column(db.BigInteger(),nullable=False,index=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    accounts = db.relationship('Account', backref=db.backref('user', lazy=True), cascade="all, delete-orphan")
    point_cards = db.relationship('PointCard', backref=db.backref('user', lazy=True), cascade="all, delete-orphan")
    deleted = db.Column(db.Boolean(), default=False)

    query_class = QueryWithSoftDelete

    orders = db.relationship('Order', order_by="asc(Order.date_created)", backref=db.backref('user', lazy=False), cascade="all, delete-orphan",lazy=True)
    positions = db.relationship('Position', order_by="asc(Position.date_created)", backref=db.backref('user', lazy=False), cascade="all, delete-orphan",lazy=True)

    def account(self):
        return next((account for account in self.accounts if account.active), None)

    def point_card(self):
        return next((card for card in self.point_cards if card.active), None)

    def __init__(self,name="",disc_id=0):
        self.name = name
        self.disc_id = disc_id
        self.accounts.append(Account())
        self.point_cards.append(PointCard())

    def __repr__(self):
        return '<User %r>' % self.name

    def shares_value(self):
        return sum([share.units * share.stock.unit_price for share in self.shares])
        
    def balance(self):
        total_value = Decimal('0.00')
        for share in self.shares:
            total_value += share.units * share.stock.unit_price
        balance = self.account().amount + total_value
        return balance

    def points(self):
        total_value = 0
        for record in self.point_card().records:
            total_value += record.amount

        return total_value

    def current_gain(self):
        app = db.get_app()
        return self.balance() - self.account().snapshot_for_week(current_round()-1).amount
    
    def week_gain(self,week):
        snapshots = AccountSnapshot.query.join(Account.snapshots) \
                    .filter(Account.active == True, AccountSnapshot.week.in_((week,week-1)), Account.user_id == self.id) \
                    .order_by(AccountSnapshot.week).all()
        if len(snapshots) == 2:
            return snapshots[1].amount - snapshots[0].amount
        else:
            return 0

    def share_count(self):
        return sum([share.units for share in self.shares])

    def new_balance_history(self):
        bh = BalanceHistory(user=self, balance=self.balance(), shares=self.share_count())

    def active(self):
        return not self.deleted

    def activate(self):
        self.deleted = False

        for account in self.accounts:
            account.active = False
        acc = self.current_season_account()
        if acc:
            acc.active = True
        else:
            self.accounts.append(Account())

        for card in self.point_cards:
            card.active = False
        
        card = self.current_season_point_card()
        if card:
            card.active = True
        else:
            self.point_cards.append(PointCard())
        self.new_balance_history()
        db.session.commit()

    def short_name(self):
        return self.name[:-5]

    # id behind #
    def discord_id(self):
        return self.name[-4:]

    def mention(self):
        return f'<@{self.disc_id}>'

    def make_transaction(self,transaction):
        # do nothing
        if self.account().amount < transaction.price:
            raise TransactionError("Insuficient Funds")
        if transaction.confirmed:
            raise TransactionError("Double processing of transaction")

        try:
            self.account().amount = Account.amount - transaction.price
            transaction.confirm()
            self.account().transactions.append(transaction)
            db.session.commit()
        except Exception as e:
            raise TransactionError(str(e))
        else:
            logger.info(f"{self.name}: {transaction.description} for {transaction.price}")

        return transaction

    def award_points(self, points = 0, reason = ""):
        record = PointRecord()
        record.amount = points
        record.reason = reason
        self.point_card().records.append(record)

    def record_position(self, position=1):
        app = db.get_app()
        pos = Position()
        pos.position = position
        pos.week = current_round()
        pos.season = app.config['SEASON']
        self.positions.append(pos)

    def position(self,season,week):
        pos = Position.query.filter_by(user_id=self.id,week=week,season=season).one_or_none()

        if pos:
            return pos.position
        else:
            return "N/A"

    def current_season_account(self):
        app = db.get_app()
        return next((account for account in self.accounts if account.season==app.config['SEASON']), None)

    def current_season_point_card(self):
        app = db.get_app()
        return next((card for card in self.point_cards if card.season==app.config['SEASON']), None)

    @classmethod
    def get_by_discord_id(cls,id, deleted=False):
        if deleted:
            return cls.query.with_deleted().filter_by(disc_id=id).one_or_none()
        else:
            return cls.query.filter_by(disc_id=id).one_or_none()

    @classmethod
    def create(cls,name,disc_id):
        user = cls(name,disc_id)
        db.session.add(user)
        db.session.commit()
        return user

    @classmethod
    def find_all_by_name(cls,name):
        return cls.query.filter(cls.name.ilike(f'%{name}%')).all()

class BalanceHistory(Base):
    __tablename__ = 'balance_histories'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    balance = db.Column(db.Numeric(14,7), nullable=False)
    shares = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref=db.backref('balance_histories', lazy=False, cascade="all, delete-orphan"), lazy=True)

class StockHistory(Base):
    __tablename__ = 'stock_histories'
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    unit_price = db.Column(db.Numeric(14,7), nullable=False)
    unit_price_change = db.Column(db.Numeric(14,7), nullable=False, default = 0.0)
    units = db.Column(db.Integer, nullable=False)

    stock = db.relationship('Stock', backref=db.backref('histories', lazy=False, cascade="all, delete-orphan"), lazy=True)

class Stock(Base):
    __tablename__ = 'stocks'
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    race = db.Column(db.String(30), unique=False, nullable=True, index=True)
    coach = db.Column(db.String(30), unique=False, nullable=True, index=True)
    division = db.Column(db.String(30), unique=False, nullable=True, index=True)
    unit_price = db.Column(db.Numeric(14,7), nullable=False)
    unit_price_change = db.Column(db.Numeric(14,7), nullable=False, default = 0.0)
    orders = db.relationship('Order', backref=db.backref('stock', lazy=False), cascade="save-update",lazy=True)

    deleted = db.Column(db.Boolean(), default=False)

    query_class = QueryWithSoftDelete

    def last_history(self):
        last_history = None if len(self.histories) == 0 else self.histories[-1]
        return last_history
    
    def change_units_by(self,units):
        last_history = self.last_history()
        if last_history:
            last_history.units += units
            
    @classmethod
    def find_all_by_name(cls,name):
        stocks = cls.query.filter(or_(cls.name.ilike(f'%{name}%'), cls.code.ilike(f'%{name}%'), cls.race.ilike(f'%{name}%'), cls.coach.ilike(f'%{name}%'), cls.division.ilike(f'%{name}%'))).all()
        stocks = cls.add_share_data(stocks)
        return stocks

    @classmethod
    def find_top(cls,limit=10):
        stocks = cls.query.order_by(desc(cls.unit_price)).limit(limit).all()
        stocks = cls.add_share_data(stocks)
        return stocks

    @classmethod
    def find_bottom(cls,limit=10):
        stocks = cls.query.order_by(cls.unit_price).filter(cls.unit_price > 0 ).limit(limit).all()
        stocks = cls.add_share_data(stocks)
        return stocks

    @classmethod
    def find_hot(cls,limit=10):
        stocks =  cls.query.all()
        stocks = cls.add_share_data(stocks)
        sort = sorted(stocks,key=lambda x: x.share_count, reverse=True)
        return sort[0:int(limit)]

    @classmethod
    def find_net(cls,limit=10):
        stocks =  cls.query.all()
        stocks = cls.add_share_data(stocks)
        sort = sorted(stocks,key=lambda x: x.net_worth, reverse=True)
        return sort[0:int(limit)]

    @classmethod
    def find_gain(cls,limit=10):
        stocks =  cls.query.all()
        stocks = cls.add_share_data(stocks)
        sort = sorted(stocks,key=lambda x: x.unit_price_change, reverse=True)
        return sort[0:int(limit)]

    @classmethod
    def find_gain_pct(cls,limit=10):
        stocks =  cls.query.all()
        stocks = cls.add_share_data(stocks)
        sort = sorted(stocks,key=lambda x: 0 if int(x.unit_price) == 0 else x.unit_price_change / (x.unit_price - x.unit_price_change), reverse=True)
        return sort[0:int(limit)]

    @classmethod
    def find_loss(cls,limit=10):
        stocks =  cls.query.all()
        stocks = cls.add_share_data(stocks)
        sort = sorted(stocks,key=lambda x: x.unit_price_change, reverse=False)
        return sort[0:int(limit)]

    @classmethod
    def find_loss_pct(cls,limit=10):
        stocks =  cls.query.all()
        stocks = cls.add_share_data(stocks)
        sort = sorted(stocks,key=lambda x: 0 if int(x.unit_price) == 0 else x.unit_price_change / (x.unit_price - x.unit_price_change))
        return sort[0:int(limit)]

    @classmethod
    def find_by_code(cls,name):
        stock = cls.query.filter(cls.code.ilike(f'{name}')).one_or_none()
        if stock:
            stock.share_count = sum(share.units for share in stock.shares)
            stock.net_worth = stock.share_count * stock.unit_price
        return stock

    @classmethod
    def add_share_data(cls, stocks):
        for stock in stocks:
            stock.share_count = sum(share.units for share in stock.shares)
            stock.net_worth = stock.share_count * stock.unit_price
        return stocks

class Share(Base):
    __tablename__ = 'shares'

    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    units = db.Column(db.Integer,nullable=False)

    __table_args__ = (
        UniqueConstraint('stock_id', 'user_id', name='uix_stock_id_user_id'),
    )

    stock = db.relationship("Stock", backref=db.backref('shares', cascade="all, delete-orphan"), foreign_keys=[stock_id])
    user = db.relationship("User", backref=db.backref('shares', cascade="all, delete-orphan"), foreign_keys=[user_id])
    
class Order(Base):
    __tablename__ = 'orders'
    operation = db.Column(db.String(80), nullable=False)
    buy_funds = db.Column(db.Numeric(14,7), nullable=True)
    buy_shares = db.Column(db.Integer, nullable=True)
    sell_shares = db.Column(db.Integer, nullable=True)
    final_price = db.Column(db.Numeric(14,7), nullable=True)
    final_shares = db.Column(db.Integer, nullable=True)
    # price at the time of order processing
    share_price = db.Column(db.Numeric(14,7), nullable=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False, default="")
    processed = db.Column(db.Boolean, default=False, nullable=False)
    result = db.Column(db.String(255), nullable=True)
    success = db.Column(db.Boolean, default=False, nullable=False)
    season = db.Column(db.Integer, nullable=False, default=12, index = True)
    week = db.Column(db.Integer, nullable=False, index = True)

    transaction = db.relationship('Transaction',uselist=False, backref=db.backref('order', lazy=True), cascade="all, delete-orphan",lazy=False)

    def desc(self):
        app = db.get_app()
        if self.operation in ["buy"]:
            if self.buy_funds:
                desc = f"Buy {self.stock.code} ({self.stock.name}) for up to {round(self.buy_funds,0)} {app.config['CREDITS']} or up to {app.config['MAX_SHARE_UNITS']} owned shares limit"
            elif self.buy_shares:
                desc = f"Buy {self.stock.code} ({self.stock.name}) for up to {self.buy_shares} new shares or up to {app.config['MAX_SHARE_UNITS']} owned shares limit"
            else:
                desc = f"Buy {self.stock.code} ({self.stock.name}) for all available {app.config['CREDITS']} or up to {app.config['MAX_SHARE_UNITS']} owned shares limit"
        if self.operation in ["sell"]:
            if self.sell_shares:
                desc = f"Sell up to {self.sell_shares} units of {self.stock.code} ({self.stock.name})"
            else:
                desc = f"Sell all units of {self.stock.code} ({self.stock.name})"
        return desc

class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = (db.UniqueConstraint('user_id', 'season'), )
    INIT_CASH = 30000.0
    amount = db.Column(db.Numeric(14,7), default=INIT_CASH, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    season = db.Column(db.Integer, nullable=False, default=12, index = True)

    transactions = db.relationship('Transaction', backref=db.backref('account', lazy=False), cascade="all, delete-orphan",lazy=False)

    def __init__(self):
        app = db.get_app()
        self.season = app.config['SEASON']
        self.amount = Decimal(self.INIT_CASH)
        self.make_snapshot(current_round()-1)

    def __repr__(self):
        return '<Account %r>' % self.amount

    def reset(self):
        self.amount = self.__class__.INIT_CASH

    def make_snapshot(self,week):
        snap = self.snapshot_for_week(week)
        user = self.user
        if user:
            snap.amount = self.user.balance()
        else:
            snap.amount = self.INIT_CASH
        snap.week = week
        self.snapshots.append(snap)

    def snapshot_for_week(self,week):
        return next((snap for snap in self.snapshots if snap.week==week), AccountSnapshot())

class AccountSnapshot(Base):
    __tablename__ = 'account_snapshots'
    __table_args__ = (db.UniqueConstraint('account_id', 'week'), )
    amount = db.Column(db.Numeric(14,7), nullable=False)
    week = db.Column(db.Integer, nullable=False, index = True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))

    account = db.relationship('Account', backref=db.backref('snapshots', lazy=False, cascade="all, delete-orphan"), lazy=True)

class Transaction(Base):
    __tablename__ = 'transactions'

    date_confirmed = db.Column(db.DateTime,  nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    price = db.Column(db.Integer, default=0, nullable=False)
    confirmed = db.Column(db.Boolean, default = False, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))

    def confirm(self):
        self.confirmed = True
        self.date_confirmed = datetime.datetime.now()

class TransactionError(Exception):
    pass

class PointCard(Base):
    __tablename__ = 'point_cards'
    __table_args__ = (db.UniqueConstraint('user_id', 'season'), )
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    season = db.Column(db.Integer, nullable=False, default=12, index = True)

    records = db.relationship('PointRecord', backref=db.backref('card', lazy=False), cascade="all, delete-orphan",lazy=False)

    def __init__(self):
        app = db.get_app()
        self.season = app.config['SEASON']
        
class PointRecord(Base):
    __tablename__ = 'point_records'
    card_id = db.Column(db.Integer, db.ForeignKey('point_cards.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)

class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (db.Index('ix_position_season_weak_user', 'user_id', 'season', 'week', unique=True), )
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False, default=12, index = True)
    week = db.Column(db.Integer, nullable=False, index = True)

class Match(Base):
    __tablename__ = 'matches'

    division = db.Column(db.String(255), nullable=False)
    round = db.Column(db.Integer, nullable=False, index=True)
    match_uuid = db.Column(db.String(255), nullable=True)
    homeCoachId = db.Column(db.Integer, nullable=True)
    homeTeamId = db.Column(db.Integer, nullable=True)
    homeCoachName = db.Column(db.String(255), nullable=True, index=True)
    homeTeamName = db.Column(db.String(255), nullable=False, index=True)
    homeTeamRace = db.Column(db.String(255), nullable=False)
    homeScore = db.Column(db.Integer, nullable=True)

    awayCoachId = db.Column(db.Integer, nullable=True)
    awayTeamId = db.Column(db.Integer, nullable=True)
    awayCoachName = db.Column(db.String(255), nullable=True, index=True)
    awayTeamName = db.Column(db.String(255), nullable=False, index=True)
    awayTeamRace = db.Column(db.String(255), nullable=False)
    awayScore = db.Column(db.Integer, nullable=True)