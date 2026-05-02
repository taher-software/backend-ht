from src.app.db.orm import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Float
from sqlalchemy.orm import relationship
from src.app.db.orm import get_utc_time


class RoomReceptionSurvey(Base):
    __tablename__ = "room_reception_survey"

    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), index=True)
    guest_phone_number = Column(
        ForeignKey("guest.phone_number", ondelete="CASCADE"), index=True
    )
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
        DateTime(timezone=True), index=True, nullable=False, default=get_utc_time
    )
    updated_at = Column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=get_utc_time,
        onupdate=get_utc_time,
    )

    # Relationships
    namespace = relationship("Namespace", back_populates="room_reception_surveys")
    guest = relationship("Guest", back_populates="room_reception_surveys")
    room = relationship("Room", back_populates="room_reception_surveys")
    stay = relationship("Stay", back_populates="room_reception_surveys")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
