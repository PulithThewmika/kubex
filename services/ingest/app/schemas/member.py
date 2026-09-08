from datetime import datetime

from pydantic import BaseModel


class MemberResponse(BaseModel):
    user_id: str
    login: str
    avatar_url: str | None
    role: str
    joined_at: datetime
