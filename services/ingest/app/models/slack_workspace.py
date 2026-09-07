from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SlackWorkspace(Base):
    """One per-org OAuth install of the KubeX Slack app (E23-T5).

    bot_token_encrypted holds a Fernet ciphertext of the workspace bot
    token — the DB never sees the plaintext. No ORM relationship to
    Organization on purpose: the org_id FK omits ON DELETE CASCADE
    (CLAUDE.md decision 9) and an ``all, delete`` relationship would
    undo that.
    """

    __tablename__ = "slack_workspaces"
    __table_args__ = (
        Index(
            "uq_slack_workspaces_active_per_org",
            "org_id",
            unique=True,
            postgresql_where=text("uninstalled_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    slack_team_id: Mapped[str] = mapped_column(Text, nullable=False)
    slack_team_name: Mapped[str | None] = mapped_column(Text)
    bot_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    bot_user_id: Mapped[str | None] = mapped_column(Text)
    connected_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    uninstalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
