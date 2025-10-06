"""Cluster models."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Cluster(Base):
    """Cluster model."""

    __tablename__ = "clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class FileCluster(Base):
    """File to cluster mapping."""

    __tablename__ = "file_clusters"

    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), primary_key=True)
