from src.app.db.orm import Base
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from src.app.db.orm import get_utc_time
from sqlalchemy.orm import relationship


class Room(Base):
    __tablename__ = "room"
    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(
        ForeignKey("namespace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_number = Column(String(255), nullable=False, index=True)
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
    namespace = relationship("Namespace", back_populates="rooms")
    stays = relationship("Stay", back_populates="room")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
