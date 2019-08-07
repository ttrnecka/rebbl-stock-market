"""resets coaches and tournaments in DB"""
from sqlalchemy.orm.attributes import flag_modified
from web import db, create_app
from models.data_models import User

app = create_app()
app.app_context().push()

for user in User.query.with_deleted().all():
    db.session.delete(user)

db.session.commit()
