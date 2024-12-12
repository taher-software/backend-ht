from app.db.orm import Base
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.orm import get_utc_time


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
    country = Column(String(255), index=True)
    province = Column(String(255), index=True, nullable=True)
    postal_code = Column(String(255), index=True)
    city = Column(String(255), index=True, nullable=True)
    number_of_rooms = Column(Integer, index=True, nullable=True)
    confirmed_account = Column(Boolean, index=True, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=False), index=True, nullable=False, default=get_utc_time
    )
    updated_at = Column(
        DateTime(timezone=False),
        index=True,
        default=get_utc_time,
        onupdate=get_utc_time,
    )

    users = relationship("Users", back_populates="namespace")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
