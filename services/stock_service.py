"""StockService helpers"""
import re
from decimal import Decimal, getcontext

from models.data_models import Stock, Share, User, StockHistory
from models.base_model import db
from .sheet_service import SheetService

class StockService:
    non_alphanum_regexp = re.compile('[^a-zA-Z0-9]')
    division_replace_regexp = re.compile('(Season \d+\s+- Division\s+)|(#N\/A)')
    @classmethod
    def update(cls):
        getcontext().prec = 14
        stocks = SheetService.stocks(refresh=True)
        for stock in stocks:
            if not stock['Team(Sorted A-Z)'] or stock['Current Value']=="#DIV/0!":
                continue
            st = stock['Team(Sorted A-Z)']
            db_stock = Stock.query.filter_by(name=st).one_or_none()
            new_history = True
            if not db_stock:
                db_stock = Stock()
                db_stock.unit_price = Decimal(stock['Current Value'])
                change = 0
                db.session.add(db_stock)
            else:
                if round(db_stock.unit_price,2) == round(Decimal(stock['Current Value']),2):
                    change = db_stock.unit_price_change
                    new_history = False
                else:
                    change = Decimal(stock['Current Value']) - Decimal(db_stock.unit_price)
            unit_price = round(Decimal(stock['Current Value']), 7)
            stock_dict = {
                'name': stock['Team(Sorted A-Z)'],
                'unit_price': unit_price,
                'code': cls.non_alphanum_regexp.sub('', stock['Code']),
                'unit_price_change': Decimal(change),
                'race':stock['Race'],
                'coach':stock['Coach'],
                'division': f"{stock['Region']}{cls.division_replace_regexp.sub('', stock['Division'])}",
            }
            db_stock.update(**stock_dict)

            if new_history:
                last_history = db_stock.last_history()
                if last_history:
                    sh = StockHistory(unit_price=db_stock.unit_price, unit_price_change=db_stock.unit_price_change, units=last_history.units)
                else:
                    sh = StockHistory(unit_price=db_stock.unit_price, unit_price_change=0, units=0)
                db_stock.histories.append(sh)
        db.session.commit()

    @classmethod
    def add(cls, user, stock, shares):
        share = Share.query.join(Share.user, Share.stock).filter(User.id == user.id, Stock.id == stock.id).one_or_none()
        if share:
            share.units += shares
        else:
            share = Share()
            share.stock = stock
            share.user = user
            share.units = shares
        share.stock.change_units_by(shares)
        db.session.commit()
        return shares

    @classmethod
    def remove(cls, user, stock, shares):
        share = Share.query.join(Share.user, Share.stock).filter(User.id == user.id, Stock.id == stock.id).one_or_none()
        if share:
            units = share.units
            left = False
            if shares < units:
                units = shares
                left = True
            
            share.units -= units
            if not left:
                db.session.delete(share)
            share.stock.change_units_by(-1*units)
            db.session.commit()
            return units
        return 0