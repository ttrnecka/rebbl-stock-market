"""Coach service helpers"""
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import event

from models.data_models import User, Transaction
from models.base_model import db

from misc.helpers import leaderboard

class UserService:
    """UserService helpers namespace"""

    @staticmethod
    def new_coach(name, discord_id):
        user = User.create(str(name), discord_id)
        return user

    @staticmethod
    def order_by_points(limit=10,reversed=True):
        return UserService.__order("points",limit=limit,reversed=reversed)
    
    @staticmethod
    def order_by_balance(limit=10,reversed=True):
        return UserService.__order("balance",limit=limit,reversed=reversed)

    @staticmethod
    def order_by_current_gain(limit=10,reversed=True):
        return UserService.__order("current_gain",limit=limit,reversed=reversed)

    @staticmethod
    def __order(method,limit=10,reversed=False):

        users = User.query.all()

        user_tuples = []
        for user in users:
            user_tuples.append((getattr(user, method)(), user))

        sorted_users = sorted(user_tuples, key=lambda x: x[0], reverse=reversed)

        sorted_users = leaderboard(sorted_users,limit)
        
        return sorted_users

    @staticmethod
    def week_gain(week,limit=10):

        users = User.query.all()

        user_tuples = []
        for user in users:
            user_tuples.append((user.week_gain(week), user))

        sorted_users = sorted(user_tuples, key=lambda x: x[0], reverse=True)

        sorted_users = leaderboard(sorted_users,limit)

        return sorted_users