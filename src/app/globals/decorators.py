from functools import wraps
from app.db.orm import get_db


def transactional(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        db_generator = get_db()
        db = next(db_generator)
        try:
            result = func(*args, **kwargs, db=db)
            db.commit()
            db.flush()
            return result
        except Exception as e:
            print("---------problem occured---------")

            db.rollback()
            raise e

    return wrapper
