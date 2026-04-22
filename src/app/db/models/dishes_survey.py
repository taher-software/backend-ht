from src.app.db.orm import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Float
from sqlalchemy.orm import relationship
from src.app.db.orm import get_utc_time


class DishesSurvey(Base):
    __tablename__ = "dishes_survey"

    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), index=True)
    guest_phone_number = Column(
        ForeignKey("guest.phone_number", ondelete="CASCADE"), index=True
    )
    dish_id = Column(ForeignKey("dishes.id", ondelete="CASCADE"), index=True)
    stay_id = Column(
        ForeignKey("stay.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Survey Question - required float field
    Q = Column(Float, nullable=False)

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
    namespace = relationship("Namespace", back_populates="dishes_surveys")
    guest = relationship("Guest", back_populates="dishes_surveys")
    dish = relationship("Dishes", back_populates="surveys")
    stay = relationship("Stay", back_populates="dishes_surveys")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
