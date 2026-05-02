from src.app.db.orm import Base, get_utc_time
from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    String,
    Enum as SAEnum,
    DATE,
)
from sqlalchemy.orm import relationship
from src.app.globals.enum import MealEnum


class Meal(Base):
    __tablename__ = "meal"

    id = Column(Integer, primary_key=True, index=True)
    meal_type = Column(
        SAEnum(MealEnum), name="meal_type_enum", nullable=False, index=True
    )
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), index=True)
    meal_date = Column(DATE(), index=True, nullable=False)
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

    namespace = relationship("Namespace", back_populates="meals")
    menus = relationship("Menu", back_populates="meal_item")

    def to_dict(self):
        result = dict()
        for column in self.__table__.columns:
            if column.name == "meal_type_enum":
                result["meal_type_enum"] = getattr(self, "meal_type")
            else:
                result[column.name] = getattr(self, column.name)

        return result
