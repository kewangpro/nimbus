from sqlalchemy import Column, ForeignKey, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db.base import Base

class IssueEmbedding(Base):
    __tablename__ = "issue_embeddings"

    issue_id = Column(UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True)
    embedding = Column(Vector(768)) # Nomic Embed Text dimensions
    content_hash = Column(String(64), nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
