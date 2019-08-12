"""resets coaches and tournaments in DB"""
from sqlalchemy.orm.attributes import flag_modified
from web import db, create_app
from models.data_models import User, Stock

app = create_app()
app.app_context().push()

for user in User.query.with_deleted().all():
    db.session.delete(user)

for stock in Stock.query.all():
    db.session.delete(stock)

db.session.commit()
