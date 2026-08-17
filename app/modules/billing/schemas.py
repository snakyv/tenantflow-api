from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class CheckoutRequest(BaseModel):
    plan: str = Field(pattern=r"^(pro|business)$")
    success_url: HttpUrl
    cancel_url: HttpUrl


class CheckoutResponse(BaseModel):
    session_id: str
    checkout_url: str


class PortalRequest(BaseModel):
    return_url: HttpUrl


class PortalResponse(BaseModel):
    session_id: str
    portal_url: str


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    current_period_end: datetime | None
