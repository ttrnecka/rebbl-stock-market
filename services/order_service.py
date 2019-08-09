"""OrderService helpers"""

from models.data_models import Stock, Order, User, Share, Transaction, TransactionError
from models.base_model import db

class OrderError(Exception):
    pass

class OrderService:
    MAX_SHARE_UNITS = 10
    __open = True

    @classmethod
    def open(cls):
        cls.__open = True
    
    @classmethod
    def close(cls):
        cls.__open = False
    
    @classmethod
    def is_open(cls):
        return cls.__open
    
    @classmethod
    def create(cls, user, stock, **kwargs):
        if not cls.is_open():
            raise OrderError("Market is closed!!!")

        share = Share.query.join(Share.user, Share.stock).filter(User.id == user.id, Stock.id == stock.id).one_or_none()
        if share and share.units >= cls.MAX_SHARE_UNITS:
            raise OrderError(f"You already own {cls.MAX_SHARE_UNITS} shares of {stock.code}")

        order = Order(**kwargs)
        user.orders.append(order)
        order.stock = stock

        if kwargs['operation'] in ["buy"]:
            if kwargs.get('buy_funds', None):
                order.description = f"Buy {stock.code} ({stock.name}) for up to {kwargs['buy_funds']} credits or up to {cls.MAX_SHARE_UNITS} owned shares limit"
            else:
                order.description = f"Buy {stock.code} ({stock.name}) for all available credits or up to {cls.MAX_SHARE_UNITS} owned shares limit"
        if kwargs['operation'] in ["sell"]:
            if kwargs.get('sell_shares', None):
                order.description = f"Sell up to {kwargs['sell_shares']} units of {stock.code} ({stock.name})"
            else:
                order.description = f"Sell all units of {stock.code} ({stock.name})"
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
        if order.operation == "buy":
            # sets the order stock price at the time of processing
            order.share_price = order.stock.unit_price
            funds = order.user.account.amount
            if order.buy_funds and order.buy_funds < funds:
                funds = order.buy_funds
            
            if order.stock.unit_price:
                share = Share.query.join(Share.user, Share.stock).filter(User.id == order.user.id, Stock.id == order.stock.id).one_or_none()
                shares = funds // order.stock.unit_price

                possible_shares = cls.MAX_SHARE_UNITS
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
                    order.result = f"Bought {order.final_shares} {order.stock.code} share(s) for {round(order.final_price, 2)} credits"
                    tran = Transaction(order=order, price=order.final_price, description=order.result)
                else:
                    order.success = False
                    order.result = f"Not enough funds to buy any shares or {cls.MAX_SHARE_UNITS} share limit reached"
            else:
                order.success = False
                order.result = "Cannot buy stock with 0 price"
            order.processed = True
            
        if order.operation == "sell":
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
                order.result = f"Sold {order.final_shares} {order.stock.code} share(s) for {round(order.final_price, 2)} credits"
                tran = Transaction(order=order, price=-1*order.final_price, description=order.result)
            else:
                order.success = False
                order.result = "No shares left to sell"
            order.processed = True
        
        if order.success:
            try:
                order.user.make_transaction(tran)
            except TransactionError as exc:
                order.success = False
                order.result = str(exc)
        db.session.commit()
        return order