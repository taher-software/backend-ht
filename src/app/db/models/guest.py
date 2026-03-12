from src.app.db.orm import Base
from sqlalchemy import Column, String, Integer, DateTime, Boolean, PickleType, DATE
from datetime import datetime
from src.app.db.orm import get_utc_time
from sqlalchemy.orm import relationship
from src.settings import settings


class Guest(Base):
    __tablename__ = "guest"
    phone_number = Column(String(255), primary_key=True, index=True)
    first_name = Column(String(255), nullable=True, index=True)
    last_name = Column(String(255), nullable=True)
    birth_date = Column(DATE, nullable=True)
    avatar_url = Column(String(255), default=settings.default_profile)
    current_device_token = Column(String(255), nullable=True)
    pref_language = Column(String(255), nullable=True)
    nationality = Column(String(255), nullable=True)
    country_of_residence = Column(String(255), nullable=True)
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

    daily_room_surveys = relationship(
        "DailyRoomSatisfactionSurvey", back_populates="guest"
    )
    room_reception_surveys = relationship("RoomReceptionSurvey", back_populates="guest")
    queue_root_causes = relationship("QueueRootCause", back_populates="guest")
    daily_restaurant_surveys = relationship(
        "DailyRestaurantSurvey", back_populates="guest"
    )
    dishes_surveys = relationship("DishesSurvey", back_populates="guest")
    chat_rooms = relationship("ChatRoom", back_populates="guest")
    stays = relationship("Stay", back_populates="guest")
    claims = relationship("Claim", back_populates="guest")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
