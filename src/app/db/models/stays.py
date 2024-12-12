from src.app.db.orm import Base
from sqlalchemy import Column, ForeignKey, DateTime, String, Integer
from datetime import datetime
from src.app.db.orm import get_utc_time


class Stay(Base):
    __tablename__ = "stay"
    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id"))
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    guest_id = Column(ForeignKey("guest.phone_number"))
    meal_plan = Column(String(255))
    stay_room = Column(String(255), nullable=False)
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
