from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .cluster import Cluster


class ClusterQuery(Base):
    __tablename__ = "cluster_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False
    )
    promql: Mapped[str] = mapped_column(Text, nullable=False)
    # kind/params (#840, migration V032 - self-sufficient, doesn't require
    # V031 to have landed first): "instant" (default) or "range" for
    # Prometheus, "logql" for Loki. params carries the extra fields a
    # range/logql query needs (start/end/step or start/end/limit/direction)
    # that a bare instant query doesn't.
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="instant")
    params: Mapped[Any | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    result: Mapped[Any | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cluster: Mapped[Cluster] = relationship(back_populates="queries")
