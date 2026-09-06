from datetime import datetime

from pydantic import BaseModel


class ApiKeyCreateRequest(BaseModel):
    name: str


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    token: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    last_used: datetime | None
