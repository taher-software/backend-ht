from src.app.db.orm import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from src.app.db.orm import get_utc_time


class DailyRoomSatisfactionSurvey(Base):
    __tablename__ = "daily_room_satisfaction_survey"

    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), index=True)
    guest_phone_number = Column(
        ForeignKey("guest.phone_number", ondelete="CASCADE"), index=True
    )
    housekeeper_id = Column(ForeignKey("housekeepers.id", ondelete="SET NULL"), nullable=True, index=True)
    room_id = Column(ForeignKey("room.id", ondelete="SET NULL"), nullable=True, index=True)
    stay_id = Column(
        ForeignKey("stay.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Survey Questions - changed to Float and made nullable
    Q1 = Column(Float, nullable=True)  # Removed index
    Q2 = Column(Float, nullable=True)
    Q3 = Column(Float, nullable=True)
    Q4 = Column(Float, nullable=True)

    # Timestamps
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

    # Relationships
    namespace = relationship("Namespace", back_populates="daily_room_surveys")
    guest = relationship("Guest", back_populates="daily_room_surveys")
    room = relationship("Room", back_populates="daily_room_surveys")
    stay = relationship("Stay", back_populates="daily_room_surveys")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
