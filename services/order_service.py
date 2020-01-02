"""OrderService helpers"""
import json
import os

from models.data_models import Stock, Order, User, Share, Transaction, TransactionError, StockHistory
from models.base_model import db

class OrderError(Exception):
    pass

class Config:
    FILE = f"{os.path.dirname(os.path.realpath(__file__))}/../config/config.json"
    """TradeService service namespace"""
    
    @classmethod
    def read_config(cls):
        with open(cls.FILE, 'r') as f:
            config = json.load(f)
        return config

    @classmethod
    def write_config(cls,config):
        with open(cls.FILE, 'w') as f:
            json.dump(config, f)

class OrderService:
    @classmethod
    def close(cls):
        cls.__change(True)

    @classmethod
    def open(cls):
        cls.__change(False)

    @classmethod
    def is_open(cls):
        config = Config.read_config()
        return not config['market_closed']

    @classmethod
    def __change(cls,state):
        config = Config.read_config()
        config['market_closed'] = state
        Config.write_config(config)
    
    @classmethod
    def create(cls, user, stock, **kwargs):
        app = db.get_app()
        if not cls.is_open():
            raise OrderError("Market is closed!!!")
        
        if kwargs['operation'] in ["buy"]:
            share = Share.query.join(Share.user, Share.stock).filter(User.id == user.id, Stock.id == stock.id).one_or_none()
            if share and share.units >= app.config['MAX_SHARE_UNITS']:
                raise OrderError(f"You already own {app.config['MAX_SHARE_UNITS']} shares of {stock.code}")

        order = Order(**kwargs)
        user.orders.append(order)
        order.stock = stock
        db.session.commit()
        return order

    @classmethod
    def cancel(cls, order_id, user):
        if not cls.is_open():
            raise OrderError("Market is closed!!!")

        order = Order.query.join(Order.user).filter(User.id == user.id, Order.processed == False, Order.id == int(order_id)).first()

        if order:
            db.session.delete(order)
            db.session.commit()
            return True
        else:
            return False
    
    @classmethod
    def process(cls, order):
        stock_modifier = 1
        app = db.get_app()
        if order.operation == "buy":
            # sets the order stock price at the time of processing
            order.share_price = order.stock.unit_price
            funds = order.user.account.amount
            if order.buy_funds and order.buy_funds < funds:
                funds = order.buy_funds
            
            if order.stock.unit_price:
                share = Share.query.join(Share.user, Share.stock).filter(User.id == order.user.id, Stock.id == order.stock.id).one_or_none()
                
                shares = funds // order.stock.unit_price
                # if shares limited and they are less than max use them instead
                if order.buy_shares and shares > order.buy_shares:
                    shares = order.buy_shares
                
                possible_shares = app.config['MAX_SHARE_UNITS']
                if share:
                    possible_shares -= share.units
                
                if possible_shares < shares:
                    shares = possible_shares

                order.final_shares = shares
                order.final_price = shares * order.stock.unit_price
                if shares:
                    if share:
                        share.units = Share.units + shares
                    else:
                        share = Share()
                        share.stock = order.stock
                        share.user = order.user
                        share.units = shares

                    order.success = True
                    order.result = f"Bought {order.final_shares} {order.stock.code} share(s) for {round(order.final_price, 2)} {app.config['CREDITS']}"
                    tran = Transaction(order=order, price=order.final_price, description=order.result)
                else:
                    order.success = False
                    order.result = f"Not enough funds to buy any shares of {order.stock.code} or {app.config['MAX_SHARE_UNITS']} share limit reached"
            else:
                order.success = False
                order.result = "Cannot buy stock with 0 price"
            order.processed = True
            
        if order.operation == "sell":
            stock_modifier = -1
            # sets the order stock price at the time of processing
            order.share_price = order.stock.unit_price
            share = Share.query.join(Share.user, Share.stock).filter(User.id == order.user.id, Stock.id == order.stock.id).one_or_none()
            if share:
                units = share.units
                left = False
                if order.sell_shares and order.sell_shares < units:
                    units = order.sell_shares
                    left = True
                
                funds = units * order.stock.unit_price

                order.final_shares = units
                order.final_price = funds

                share.units = Share.units - units
                if not left:
                    db.session.delete(share)

                order.success = True
                order.result = f"Sold {order.final_shares} {order.stock.code} share(s) for {round(order.final_price, 2)} {app.config['CREDITS']}"
                tran = Transaction(order=order, price=-1*order.final_price, description=order.result)
            else:
                order.success = False
                order.result = f"No shares of {order.stock.code} left to sell"
            order.processed = True
        
        if order.success:
            try:
                order.user.make_transaction(tran)
            except TransactionError as exc:
                order.success = False
                order.result = str(exc)

            order.stock.change_units_by(stock_modifier*order.final_shares)
        db.session.commit()
        return order