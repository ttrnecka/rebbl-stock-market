"""StockService helpers"""
import re

from models.data_models import Stock
from models.base_model import db
from .sheet_service import SheetService

class StockService:
    non_alphanum_regexp = re.compile('[^a-zA-Z0-9]')
    @classmethod
    def update(cls):
        stocks = SheetService.stocks(refresh=True)
        for stock in stocks:
            db_stock = Stock.query.filter_by(name=stock['Stock']).one_or_none()
            if not db_stock:
                db_stock = Stock()
            stock_dict = {
                'name':stock['Stock'],
                'unit_price':stock['Value'],
                'code': cls.non_alphanum_regexp.sub('', stock['Code'])
            }
            db_stock.update(**stock_dict)
            db.session.add(db_stock)
        db.session.commit()
    