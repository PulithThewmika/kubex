from datetime import datetime

from pydantic import BaseModel


class InstallationResponse(BaseModel):
    id: str
    github_installation_id: int
    account_login: str
    repos: list[str]
    status: str
    created_at: datetime
