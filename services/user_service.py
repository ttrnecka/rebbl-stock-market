"""Coach service helpers"""
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import event

from models.data_models import User, Transaction
from models.base_model import db

class UserService:
    """CoachService helpers namespace"""

    @staticmethod
    def new_coach(name, discord_id):
        user = User.create(str(name), discord_id)
        db.session.add(user)
        return user

    