"""Various helpers"""
from flask import session
from sqlalchemy.orm import raiseload

from models.data_models import User


def represents_int(string):
    """Check if the `s` is int"""
    try:
        int(string)
        return True
    except ValueError:
        return False