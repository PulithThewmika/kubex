from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NotificationChannel(Base):
    """A Slack channel that receives KubeX events for an org (E23-T5).

    ``service_id IS NULL`` routes every service in the org; a real id
    scopes to one. ``event_types`` is a JSONB string array — v1 only
    emits ``"deploy_health"``.
    """

    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("slack_workspaces.id", ondelete="CASCADE"), nullable=False
    )
    slack_channel_id: Mapped[str] = mapped_column(Text, nullable=False)
    slack_channel_name: Mapped[str] = mapped_column(Text, nullable=False)
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE")
    )
    event_types: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default='["deploy_health"]'
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_delivery_error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
