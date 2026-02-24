from src.app.db.orm import Base
from sqlalchemy import Column, ForeignKey, DateTime, String, Integer, DATE
from datetime import datetime
from src.app.db.orm import get_utc_time
from sqlalchemy.orm import relationship


class Stay(Base):
    __tablename__ = "stay"
    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), index=True)
    start_date = Column(DATE, nullable=False, index=True)
    end_date = Column(DATE, nullable=False, index=True)
    guest_id = Column(ForeignKey("guest.phone_number", ondelete="CASCADE"), index=True)
    meal_plan = Column(String(255), nullable=False)
    room_id = Column(
        ForeignKey("room.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
    guest = relationship("Guest", back_populates="stays")
    room = relationship("Room", back_populates="stays")
    claims = relationship("Claim", back_populates="stay")
    chat_rooms = relationship("ChatRoom", back_populates="stay")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
