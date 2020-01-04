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

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass
    
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    
    return False

def leaderboard(sorted_tuple_list,max_position=1):
    """Provided sorted tuple by index 0 value returns new tuple with index as leaderboard position"""
    last_value = None
    last_position = None
    new_list = []
    for i, (value, *rest) in enumerate(sorted_tuple_list):
        if last_value and value == last_value:
            position = last_value
        else:
            position = i + 1
        
        if max_position < position:
            break
        new_list.append((position,value,*rest))
        last_value = value
        last_position = position

    return new_list
