"""resets coaches and tournaments in DB"""
from web import db, create_app
from models.data_models import Stock, BalanceHistory, User

app = create_app()
app.app_context().push()
users = User.query.all()

for user in users:
    bh = BalanceHistory(balance=user.balance(), shares=user.share_count())
    user.balance_histories = []
    user.balance_histories.append(bh)

db.session.commit()
