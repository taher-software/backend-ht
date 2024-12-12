from app.db.orm import Base
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    PickleType,
    ForeignKey,
    Float,
)
from datetime import datetime
from app.db.orm import get_utc_time


class Claim(Base):
    __tablename__ = "claim"
    id = Column(Integer, primary_key=True, index=True)
    guest_id = Column(ForeignKey("guest.phone_number", ondelete="CASCADE"))
    status = Column(String(255), nullable=False, default="submitted")
    stay_id = Column(ForeignKey("stay.id", ondelete="CASCADE"))
    claim_text = Column(String(1000))
    claim_title = Column(String(1000))
    claim_voice_url = Column(String(255))
    claim_voice_duration = Column(Float())
    claim_images_url = Column(PickleType)
    claim_video_url = Column(String(255))
    acknowledged_employee_id = Column(ForeignKey("users.id", ondelete="CASCADE"))
    acknowledged_claim_time = Column(DateTime, index=True, nullable=True)
    resolver_employee_id = Column(ForeignKey("users.id", ondelete="CASCADE"))
    resolve_claim_time = Column(DateTime, index=True, nullable=True)
    approve_claim_time = Column(DateTime, index=True, nullable=True)
    claim_language = Column(String(255), nullable=False)
    claim_category = Column(String(255), nullable=False)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"))
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
