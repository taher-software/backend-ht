from src.app.db.orm import Base
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from src.app.db.orm import get_utc_time


class ChatRoom(Base):
    __tablename__ = "chat_room"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    guest_id = Column(
        ForeignKey("guest.phone_number", ondelete="CASCADE"), nullable=False
    )
    claim_id = Column(ForeignKey("claim.id", ondelete="CASCADE"), nullable=False, unique=True)
    stay_id = Column(ForeignKey("stay.id", ondelete="CASCADE"), nullable=False)
    namespace_id = Column(
        ForeignKey("namespace.id", ondelete="CASCADE"), nullable=False
    )
    active = Column(Boolean, nullable=False, default=True, index=True)
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
    user = relationship("Users", back_populates="chat_rooms")
    guest = relationship("Guest", back_populates="chat_rooms")
    claim = relationship("Claim", back_populates="chat_rooms")
    stay = relationship("Stay", back_populates="chat_rooms")
    namespace = relationship("Namespace", back_populates="chat_rooms")
    messages = relationship(
        "Message",
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="desc(Message.created_at)",
    )

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
