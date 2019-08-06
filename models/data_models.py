from .base_model import db, Base, QueryWithSoftDelete
import logging
import json
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

    orders = db.relationship('Order', backref=db.backref('user', lazy=False), cascade="all, delete-orphan",lazy=True)

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

class Stock(Base):
    __tablename__ = 'stocks'
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    unit_price = db.Column(db.Float, nullable=False)
    orders = db.relationship('Order', backref=db.backref('stock', lazy=False), cascade="save-update",lazy=True)

    @classmethod
    def find_all_by_name(cls,name):
        return cls.query.filter(cls.name.ilike(f'%{name}%')).all()

class Order(Base):
    __tablename__ = 'orders'
    operation = db.Column(db.String(80), nullable=False)
    buy_funds = db.Column(db.Float, nullable=True)
    sell_shares = db.Column(db.Integer, nullable=True)
    final_price = db.Column(db.Float, nullable=True)
    final_shares = db.Column(db.Integer, nullable=True)
    # price at the time of order processing
    share_price = db.Column(db.Float, nullable=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    processed = db.Column(db.Boolean, default=False, nullable=False)

class Account(Base):
    __tablename__ = 'accounts'
    INIT_CASH = 3000
    amount = db.Column(db.Integer, default=INIT_CASH, nullable=False)
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
