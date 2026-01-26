from sqlalchemy import Boolean, Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum

from app.db.base import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    CLIENT = "client"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    role = Column(String, default=UserRole.MEMBER, nullable=False)
    timezone = Column(String, default="UTC", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())