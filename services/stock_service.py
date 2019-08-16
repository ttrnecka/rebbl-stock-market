"""StockService helpers"""
import re
from decimal import Decimal

from models.data_models import Stock
from models.base_model import db
from .sheet_service import SheetService

class StockService:
    non_alphanum_regexp = re.compile('[^a-zA-Z0-9]')
    @classmethod
    def update(cls):
        stocks = SheetService.stocks(refresh=True)
        for stock in stocks:
            if not stock['Team(Sorted A-Z)']:
                continue
            st = f"'{stock['Team(Sorted A-Z)']}'"
            db_stock = Stock.query.filter_by(name=st).one_or_none()
            if not db_stock:
                db_stock = Stock()
                db_stock.unit_price = Decimal(stock['Current Value'])
                change = 0
            else:
                if db_stock.unit_price == Decimal(stock['Current Value']):
                    change = db_stock.unit_price_change
                else:
                    change = Decimal(stock['Current Value']) - db_stock.unit_price,

            stock_dict = {
                'name':stock['Team(Sorted A-Z)'],
                'unit_price':stock['Current Value'],
                'code': cls.non_alphanum_regexp.sub('', stock['Code']),
                'unit_price_change': change,
                'race':stock['Race'],
                'coach':stock['Coach'],
            }
            db_stock.update(**stock_dict)
            db.session.add(db_stock)
        db.session.commit()
    