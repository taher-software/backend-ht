from src.app.db.orm import Base
from sqlalchemy import Column, String, Integer, DateTime, Boolean, PickleType
from datetime import datetime
from src.app.db.orm import get_utc_time

default_profile = "https://static.vecteezy.com/system/resources/thumbnails/009/734/564/small/default-avatar-profile-icon-of-social-media-user-vector.jpg"


class Guest(Base):
    __tablename__ = "guest"
    phone_number = Column(String(255), primary_key=True, index=True)
    first_name = Column(String(255), nullable=False, index=True)
    last_name = Column(String(255), nullable=False)
    birth_date = Column(DateTime, nullable=True)
    avatar_url = Column(String(255), default=default_profile)
    current_device_token = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=False), index=True, nullable=False, default=get_utc_time
    )
    updated_at = Column(
        DateTime(timezone=False),
        index=True,
        nullable=False,
        default=get_utc_time,
        onupdate=get_utc_time,
    )

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
