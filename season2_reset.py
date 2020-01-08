"""resets coaches and tournaments in DB"""
from sqlalchemy.orm.attributes import flag_modified
from web import db, app
from models.data_models import User, Account, AccountSnapshot, Match

app.app_context().push()

Match.query.delete()

for user in User.query.all():
    user.deleted = True
    # one time action, remove next season
    snap = AccountSnapshot()
    snap.amount = 30000
    snap.week = 0
    user.account().snapshots.append(snap)
    user.account().make_snapshot(19)

db.session.commit()
