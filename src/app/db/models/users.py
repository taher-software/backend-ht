from src.app.db.orm import Base
from sqlalchemy import Column, String, Integer, DateTime, PickleType, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from src.app.db.orm import get_utc_time
from src.app.globals.schema_models import Role
from sqlalchemy import Enum


class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    namespace_id = Column(ForeignKey("namespace.id", ondelete="CASCADE"))
    phone_number = Column(String(255), unique=True, index=True, nullable=False)
    avatar_url = Column(String(255), index=True, nullable=True)
    user_email = Column(String(255), index=True)
    first_name = Column(String(255), index=True)
    last_name = Column(String(255), index=True)
    current_device_token = Column(String(255), nullable=True)
    hashed_password = Column(String(255), index=True, nullable=True)
    role = Column(String(255), index=True, nullable=False)
    created_at = Column(
        DateTime(timezone=False), index=True, nullable=False, default=get_utc_time
    )
    pref_language = Column(String(255), nullable=True)
    updated_at = Column(
        DateTime(timezone=False),
        index=True,
        nullable=False,
        default=get_utc_time,
        onupdate=get_utc_time,
    )
    namespace = relationship("Namespace", back_populates="users")
    received_claims = relationship(
        "Claim",
        back_populates="receiver",
        foreign_keys="[Claim.acknowledged_employee_id]",
    )
    resolved_claims = relationship(
        "Claim",
        back_populates="resolver",
        foreign_keys="[Claim.resolver_employee_id]",
    )

    def to_dict(self):
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
