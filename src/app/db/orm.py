from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import sqlalchemy
from src.settings import settings
from datetime import datetime
import pytz


SQLALCHEMY_DATABASE_URL = settings.db_url

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"options": "-c timezone=utc"},
    poolclass=NullPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
metadata = sqlalchemy.MetaData()


# Dependency
def get_db():
    db = None
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_utc_time():
    return datetime.now(pytz.UTC)
