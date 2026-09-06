from datetime import datetime

from pydantic import BaseModel


class InstallationResponse(BaseModel):
    id: str
    account_login: str
    repos: list[str]
    status: str
    created_at: datetime
