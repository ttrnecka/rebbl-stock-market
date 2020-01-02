"""Coach service helpers"""
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import event

from models.data_models import User, Transaction
from models.base_model import db

class UserService:
    """UserService helpers namespace"""

    @staticmethod
    def new_coach(name, discord_id):
        user = User.create(str(name), discord_id)
        return user

    @staticmethod
    def order_by_points(limit=10,reversed=True):
        return UserService.__order("points",limit)
    
    @staticmethod
    def order_by_balance(limit=10,reversed=True):
        return UserService.__order("balance",limit)

    @staticmethod
    def order_by_current_gain(limit=10,reversed=True):
        return UserService.__order("current_gain",limit)

    @staticmethod
    def __order(method,limit=10,reversed=False):

        users = User.query.all()

        user_tuples = []
        for user in users:
            user_tuples.append((getattr(user, method)(), user))

        sorted_users = sorted(user_tuples, key=lambda x: x[0], reverse=reversed)

        max = int(limit)
        if max > len(sorted_users):
            max = len(sorted_users)

        return sorted_users[0:max]

    @staticmethod
    def week_gain(week,limit=10):

        users = User.query.all()

        user_tuples = []
        for user in users:
            user_tuples.append((user.week_gain(week), user))

        sorted_users = sorted(user_tuples, key=lambda x: x[0], reverse=True)

        max = int(limit)
        if max > len(sorted_users):
            max = len(sorted_users)

        return sorted_users[0:max]