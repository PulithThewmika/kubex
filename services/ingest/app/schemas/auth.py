from pydantic import BaseModel, Field


class SwitchOrgRequest(BaseModel):
    org_id: str = Field(min_length=1)


class MeResponse(BaseModel):
    user_id: str
    login: str
    email: str | None
    avatar_url: str | None
    org_id: str
    org_name: str | None
    org_slug: str | None


class MembershipItem(BaseModel):
    org_id: str
    org_name: str
    org_slug: str
