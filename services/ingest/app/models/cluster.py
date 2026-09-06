from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .cluster_query import ClusterQuery
    from .organization import Organization
    from .service import Service


class Cluster(Base):
    __tablename__ = "clusters"
    __table_args__ = (
        UniqueConstraint("org_id", "name"),
        CheckConstraint("status IN ('pending', 'connected', 'disconnected')", name="clusters_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash_old: Mapped[str | None] = mapped_column(Text)
    token_old_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    agent_version: Mapped[str | None] = mapped_column(Text)
    argocd_version: Mapped[str | None] = mapped_column(Text)
    argocd_status: Mapped[str | None] = mapped_column(Text)
    prometheus_status: Mapped[str | None] = mapped_column(Text)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")

    organization: Mapped[Organization] = relationship(back_populates="clusters")
    services: Mapped[list[Service]] = relationship(back_populates="cluster")
    queries: Mapped[list[ClusterQuery]] = relationship(back_populates="cluster")
