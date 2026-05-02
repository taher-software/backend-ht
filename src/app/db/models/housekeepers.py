from src.app.db.orm import Base, get_utc_time
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.settings import settings


class Housekeeper(Base):
    __tablename__ = "housekeepers"

    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"), nullable=False, index=True)
    avatar_url = Column(String(255), nullable=True, default=settings.default_profile)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_time)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=get_utc_time,
        onupdate=get_utc_time,
    )

    namespace = relationship("Namespace", back_populates="housekeepers")
    assignments = relationship("HousekeeperAssignment", back_populates="housekeeper")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
