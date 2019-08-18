"""StockService helpers"""
import re
from decimal import Decimal, getcontext

from models.data_models import Stock, Share, User
from models.base_model import db
from .sheet_service import SheetService

class StockService:
    non_alphanum_regexp = re.compile('[^a-zA-Z0-9]')
    division_replace_regexp = re.compile('(Season \d+\s+- Division\s+)|(#N\/A)')
    @classmethod
    def update(cls):
        getcontext().prec = 7
        stocks = SheetService.stocks(refresh=True)
        for stock in stocks:
            if not stock['Team(Sorted A-Z)']:
                continue
            st = stock['Team(Sorted A-Z)']
            db_stock = Stock.query.filter_by(name=st).one_or_none()
            if not db_stock:
                db_stock = Stock()
                db_stock.unit_price = Decimal(stock['Current Value'])
                change = 0
                db.session.add(db_stock)
            else:
                if round(db_stock.unit_price,2) == round(Decimal(stock['Current Value']),2):
                    change = db_stock.unit_price_change
                else:
                    change = Decimal(stock['Current Value']) - Decimal(db_stock.unit_price)

            stock_dict = {
                'name':stock['Team(Sorted A-Z)'],
                'unit_price':stock['Current Value'],
                'code': cls.non_alphanum_regexp.sub('', stock['Code']),
                'unit_price_change': change,
                'race':stock['Race'],
                'coach':stock['Coach'],
                'division': f"{stock['Region']}{cls.division_replace_regexp.sub('', stock['Division'])}",
            }
            db_stock.update(**stock_dict)
        db.session.commit()

    @classmethod
    def add(cls, user, stock, shares):
        share = Share.query.join(Share.user, Share.stock).filter(User.id == user.id, Stock.id == stock.id).one_or_none()
        if share:
            share.units = Share.units + shares
        else:
            share = Share()
            share.stock = stock
            share.user = user
            share.units = shares
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
            
            share.units = Share.units - units
            if not left:
                db.session.delete(share)
            db.session.commit()
            return units
        return 0