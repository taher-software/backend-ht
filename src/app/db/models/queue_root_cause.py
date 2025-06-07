from src.app.db.orm import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Boolean
from sqlalchemy.orm import relationship
from src.app.db.orm import get_utc_time
from sqlalchemy import CheckConstraint


class QueueRootCause(Base):
    __tablename__ = "queue_root_cause"

    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), index=True)
    guest_phone_number = Column(
        ForeignKey("guest.phone_number", ondelete="CASCADE"), index=True
    )

    # Root cause fields - all optional
    r1 = Column(Boolean, nullable=True)
    r2 = Column(Boolean, nullable=True)
    r3 = Column(Boolean, nullable=True)

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
    namespace = relationship("Namespace", back_populates="queue_root_causes")
    guest = relationship("Guest", back_populates="queue_root_causes")

    # Constraint to ensure at least one root cause is selected
    __table_args__ = (
        CheckConstraint(
            "r1 IS TRUE OR r2 IS TRUE OR r3 IS TRUE",
            name="check_at_least_one_root_cause",
        ),
    )

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
