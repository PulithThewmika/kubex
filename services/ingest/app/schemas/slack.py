from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SlackChannelResponse(BaseModel):
    id: str
    slack_channel_id: str
    slack_channel_name: str
    service_id: int | None
    event_types: list[str]
    enabled: bool
    last_delivery_at: datetime | None
    last_delivery_error: str | None


class SlackConnectionResponse(BaseModel):
    connected: bool
    workspace_id: str | None = None
    team_name: str | None = None
    channels: list[SlackChannelResponse] = Field(default_factory=list)


class SlackPickerChannel(BaseModel):
    """A channel from conversations.list, for the add-channel picker."""

    slack_channel_id: str
    name: str
    is_private: bool
    is_member: bool


class AddChannelRequest(BaseModel):
    slack_channel_id: str = Field(min_length=1, max_length=64)
    slack_channel_name: str = Field(min_length=1, max_length=128)
    service_id: int | None = None
