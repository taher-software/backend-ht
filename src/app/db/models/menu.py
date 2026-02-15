from src.app.db.orm import Base, get_utc_time
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship


class Menu(Base):
    __tablename__ = "menu"

    id = Column(Integer, primary_key=True, index=True)
    dishes_id = Column(ForeignKey("dishes.id", ondelete="CASCADE"), index=True)
    meal_id = Column(ForeignKey("meal.id", ondelete="CASCADE"), index=True)
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

    dish = relationship("Dishes", back_populates="menus")
    meal_item = relationship("Meal", back_populates="menus")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
