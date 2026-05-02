from src.app.db.orm import Base
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    PickleType,
    Enum,
    Boolean,
    Float,
)
from sqlalchemy.orm import relationship
from src.app.db.orm import get_utc_time
import enum


class OwnerType(str, enum.Enum):
    guest = "guest"
    user = "user"


class MessageType(str, enum.Enum):
    text = "text"
    image = "image"
    video = "video"
    audio = "audio"


class Message(Base):
    __tablename__ = "message"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(ForeignKey("chat_room.id", ondelete="CASCADE"), nullable=False)
    namespace_id = Column(
        ForeignKey("namespace.id", ondelete="CASCADE"), nullable=False
    )
    owner_type = Column(Enum(OwnerType), nullable=False)
    message_type = Column(Enum(MessageType), nullable=False)
    seen = Column(Boolean, nullable=False, default=False, index=True)
    guest_text_version = Column(String(1000), nullable=True)
    user_text_version = Column(String(1000), nullable=True)
    guest_voice_url = Column(String(255), nullable=True)
    user_voice_url = Column(String(255), nullable=True)
    duration = Column(Float, nullable=True)
    image_url = Column(String(255), nullable=True)
    video_url = Column(String(255), nullable=True)

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
    room = relationship("ChatRoom", back_populates="messages")
    namespace = relationship("Namespace", back_populates="messages")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
