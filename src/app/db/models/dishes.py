from src.app.db.orm import Base
from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from src.app.db.orm import get_utc_time


class Dishes(Base):
    __tablename__ = "dishes"

    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), index=True)

    # Dish details
    name = Column(String(255), index=True, nullable=False)
    description = Column(Text, nullable=True)
    img_url = Column(String(255), nullable=True)

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
    namespace = relationship("Namespace", back_populates="dishes")
    surveys = relationship("DishesSurvey", back_populates="dish")
    menus = relationship("Menu", back_populates="dish")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
