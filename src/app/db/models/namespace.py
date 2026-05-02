from src.app.db.orm import Base
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from src.app.db.orm import get_utc_time


class Namespace(Base):
    __tablename__ = "namespace"
    id = Column(Integer, primary_key=True, index=True)
    hotel_name = Column(String(255), index=True)
    hotel_email = Column(String(255), index=True, nullable=True)
    hotel_phone_number = Column(String(255), index=True, nullable=True)
    hotel_website_url = Column(String(255), index=True, nullable=True)
    hotel_star_rating = Column(Integer, index=True, nullable=True)
    business_registration_number = Column(String(255), index=True)
    tax_identification_number = Column(String(255), index=True)
    country = Column(String(255), index=True, nullable=False)
    province = Column(String(255), index=True, nullable=True)
    postal_code = Column(String(255), index=True)
    city = Column(String(255), index=True, nullable=False)
    number_of_rooms = Column(Integer, index=True, nullable=True)
    confirmed_account = Column(Boolean, index=True, nullable=False, default=False)
    pref_language = Column(String(255), nullable=True)
    timezone = Column(String(50), nullable=False)

    created_at = Column(
        DateTime(timezone=True), index=True, nullable=False, default=get_utc_time
    )
    updated_at = Column(
        DateTime(timezone=True),
        index=True,
        default=get_utc_time,
        onupdate=get_utc_time,
    )

    users = relationship("Users", back_populates="namespace")
    rooms = relationship("Room", back_populates="namespace")
    settings = relationship(
        "NamespaceSettings", back_populates="namespace", uselist=False
    )
    daily_room_surveys = relationship(
        "DailyRoomSatisfactionSurvey", back_populates="namespace"
    )
    room_reception_surveys = relationship(
        "RoomReceptionSurvey", back_populates="namespace"
    )
    dishes = relationship("Dishes", back_populates="namespace")
    meals = relationship("Meal", back_populates="namespace")
    queue_root_causes = relationship("QueueRootCause", back_populates="namespace")
    daily_restaurant_surveys = relationship(
        "DailyRestaurantSurvey", back_populates="namespace"
    )
    dishes_surveys = relationship("DishesSurvey", back_populates="namespace")
    chat_rooms = relationship("ChatRoom", back_populates="namespace")
    messages = relationship("Message", back_populates="namespace")
    housekeepers = relationship("Housekeeper", back_populates="namespace")
    housekeeper_assignments = relationship(
        "HousekeeperAssignment", back_populates="namespace"
    )

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
