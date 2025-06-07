from src.app.db.orm import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Time
from sqlalchemy.orm import relationship
from src.app.db.orm import get_utc_time


class NamespaceSettings(Base):
    __tablename__ = "namespace_settings"

    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), index=True)

    # Meal times
    breakfast_start_time = Column(Time, index=True, nullable=False)
    breakfast_end_time = Column(Time, index=True, nullable=False)
    lunch_start_time = Column(Time, index=True, nullable=False)
    lunch_end_time = Column(Time, index=True, nullable=False)
    dinner_start_time = Column(Time, index=True, nullable=False)
    dinner_end_time = Column(Time, index=True, nullable=False)

    # notification setting
    restaurant_survey_time = Column(Time, index=True, nullable=False)
    room_survey_time = Column(Time, index=True, nullable=False)
    breakfast_menu_time = Column(Time, index=True, nullable=False)
    lunch_menu_time = Column(Time, index=True, nullable=False)
    dinner_menu_time = Column(Time, index=True, nullable=False)

    # Check in/out times
    check_in_time = Column(Time, index=True, nullable=False)
    check_out_time = Column(Time, index=True, nullable=False)

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

    # Relationship
    namespace = relationship("Namespace", back_populates="settings")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
