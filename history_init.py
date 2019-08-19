"""resets coaches and tournaments in DB"""
from web import db, create_app
from models.data_models import Stock, StockHistory

app = create_app()
app.app_context().push()
stocks = Stock.query.all()
stocks = Stock.add_share_data(stocks)

for stock in stocks:
    sh = StockHistory(unit_price=stock.unit_price, unit_price_change=stock.unit_price_change)
    sh.units = stock.share_count
    stock.histories = []
    stock.histories.append(sh)

db.session.commit()
