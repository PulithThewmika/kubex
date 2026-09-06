from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .alert import Alert
    from .deployment import Deployment


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        # Matches migration V018 (#792) — uniqueness is per-org, not global.
        # repo/argocd_app are also uniquely constrained per-org (partial
        # indexes, since nullable), but partial indexes have no SQLAlchemy
        # Core equivalent, so they stay migration-only per this project's
        # convention (see deployments.workflow_run_id/argocd_revision).
        UniqueConstraint("org_id", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    repo: Mapped[str | None] = mapped_column(Text)
    argocd_app: Mapped[str | None] = mapped_column(Text)
    namespace: Mapped[str] = mapped_column(String, nullable=False, server_default="default")
    prom_components: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")

    deployments: Mapped[list[Deployment]] = relationship(back_populates="service")
    alerts: Mapped[list[Alert]] = relationship(back_populates="service")
