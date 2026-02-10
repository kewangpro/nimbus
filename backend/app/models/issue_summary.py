from sqlalchemy import Column, DateTime, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class IssueSummary(Base):
    __tablename__ = "issue_summaries"

    issue_id = Column(UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True)
    summary = Column(Text, nullable=False)
    next_steps = Column(Text, nullable=False)
    content_hash = Column(String(length=64), nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
