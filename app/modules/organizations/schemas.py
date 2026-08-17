from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(pattern=r"^(admin|member|viewer)$")


class InvitationResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    status: str


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class MembershipResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: EmailStr
    full_name: str
    role: str


class MembershipRoleUpdate(BaseModel):
    role: str = Field(pattern=r"^(admin|member|viewer)$")
