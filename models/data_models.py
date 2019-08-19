from sqlalchemy import or_, UniqueConstraint, desc

from .base_model import db, Base, QueryWithSoftDelete
import logging
import json
import datetime
from logging.handlers import RotatingFileHandler
import os


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
    account = db.relationship('Account', uselist=False, backref=db.backref('coach', lazy=True), cascade="all, delete-orphan")
    deleted = db.Column(db.Boolean(), default=False)

    query_class = QueryWithSoftDelete

    orders = db.relationship('Order', order_by="asc(Order.date_created)", backref=db.backref('user', lazy=False), cascade="all, delete-orphan",lazy=True)

    def __init__(self,name="",disc_id=0):
        self.name = name
        self.disc_id = disc_id
        self.account = Account()

    def __repr__(self):
        return '<User %r>' % self.name

    def active(self):
        return not self.deleted

    def activate(self):
        self.deleted = False

    def short_name(self):
        return self.name[:-5]

    # id behind #
    def discord_id(self):
        return self.name[-4:]

    def mention(self):
        return f'<@{self.disc_id}>'

    def make_transaction(self,transaction):
        # do nothing
        if self.account.amount < transaction.price:
            raise TransactionError("Insuficient Funds")
        if transaction.confirmed:
            raise TransactionError("Double processing of transaction")

        try:
            self.account.amount = Account.amount - transaction.price
            transaction.confirm()
            self.account.transactions.append(transaction)
            db.session.commit()
        except Exception as e:
            raise TransactionError(str(e))
        else:
            logger.info(f"{self.name}: {transaction.description} for {transaction.price}")

        return transaction


    @classmethod
    def get_by_discord_id(cls,id):
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
    description = db.Column(db.String(255), nullable=False)
    processed = db.Column(db.Boolean, default=False, nullable=False)
    result = db.Column(db.String(255), nullable=True)
    success = db.Column(db.Boolean, default=False, nullable=False)

    transaction = db.relationship('Transaction',uselist=False, backref=db.backref('order', lazy=True), cascade="all, delete-orphan",lazy=False)

class Account(Base):
    __tablename__ = 'accounts'
    INIT_CASH = 30000.0
    amount = db.Column(db.Numeric(14,7), default=INIT_CASH, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    transactions = db.relationship('Transaction', backref=db.backref('account', lazy=False), cascade="all, delete-orphan",lazy=False)

    def __repr__(self):
        return '<Account %r>' % self.amount

    def reset(self):
        self.amount = self.__class__.INIT_CASH

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
