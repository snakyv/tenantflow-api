from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import OrganizationContext, require_permission
from app.core.permissions import Permission
from app.db.models import AuditLog
from app.db.session import get_session

router = APIRouter(prefix="/organizations/{organization_id}/audit", tags=["Audit"])


class AuditResponse(BaseModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: UUID | None
    actor_id: UUID | None
    metadata: dict[str, object]
    created_at: datetime


@router.get("", response_model=list[AuditResponse])
async def list_audit(
    organization_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    _: OrganizationContext = Depends(require_permission(Permission.AUDIT_READ)),
    session: AsyncSession = Depends(get_session),
) -> list[AuditResponse]:
    rows = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        AuditResponse(
            id=row.id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            actor_id=row.actor_id,
            metadata=row.metadata_json,
            created_at=row.created_at,
        )
        for row in rows
    ]
