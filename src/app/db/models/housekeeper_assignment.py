from src.app.db.orm import Base, get_utc_time
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship


class HousekeeperAssignment(Base):
    __tablename__ = "housekeeper_assignment"

    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(
        ForeignKey("namespace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id = Column(
        ForeignKey("room.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    housekeeper_id = Column(
        ForeignKey("housekeepers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=get_utc_time
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=get_utc_time,
        onupdate=get_utc_time,
    )

    namespace = relationship(
        "Namespace", back_populates="housekeeper_assignments"
    )
    room = relationship("Room", back_populates="housekeeper_assignments")
    housekeeper = relationship("Housekeeper", back_populates="assignments")

    def to_dict(self):
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
