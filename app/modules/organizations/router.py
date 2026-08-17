from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import OrganizationContext, get_current_user, require_permission
from app.core.permissions import Permission
from app.db.models import Organization, OrganizationMembership, User
from app.db.session import get_session
from app.infra.idempotency import canonical_request_hash
from app.infra.idempotency_db import acquire_idempotency, complete_idempotency
from app.modules.organizations.schemas import (
    AcceptInvitationRequest,
    InvitationResponse,
    InviteMemberRequest,
    MembershipResponse,
    MembershipRoleUpdate,
    OrganizationCreate,
    OrganizationResponse,
)
from app.modules.organizations.service import (
    accept_invitation,
    create_organization,
    invite_member,
    remove_membership,
    update_membership_role,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def membership_response(membership: OrganizationMembership, user: User) -> MembershipResponse:
    return MembershipResponse(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
    )


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: OrganizationCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=160),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationResponse:
    request_hash = canonical_request_hash(payload.model_dump(mode="json"))
    state = await acquire_idempotency(
        session,
        user_id=user.id,
        organization_id=None,
        scope=f"organization:create:{user.id}",
        key=idempotency_key,
        request_hash=request_hash,
    )
    if state.is_replay:
        if state.replay_body is None:
            raise RuntimeError("Completed idempotency record is missing its response body")
        return OrganizationResponse.model_validate(state.replay_body)
    organization = await create_organization(session, user, payload)
    response = OrganizationResponse(
        id=organization.id, name=organization.name, slug=organization.slug, role="owner"
    )
    await complete_idempotency(
        session, state.record, status_code=201, response_body=response.model_dump(mode="json")
    )
    return response


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OrganizationResponse]:
    rows = (
        await session.execute(
            select(Organization, OrganizationMembership.role)
            .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
            .where(OrganizationMembership.user_id == user.id)
            .order_by(Organization.name)
        )
    ).all()
    return [OrganizationResponse(id=org.id, name=org.name, slug=org.slug, role=role) for org, role in rows]


@router.post("/{organization_id}/invitations", response_model=InvitationResponse, status_code=201)
async def create_invitation(
    organization_id: UUID,
    payload: InviteMemberRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=160),
    context: OrganizationContext = Depends(require_permission(Permission.MEMBERS_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> InvitationResponse:
    request_hash = canonical_request_hash(payload.model_dump(mode="json"))
    state = await acquire_idempotency(
        session,
        user_id=context.user.id,
        organization_id=organization_id,
        scope=f"invitation:create:{organization_id}:{context.user.id}",
        key=idempotency_key,
        request_hash=request_hash,
    )
    if state.is_replay:
        if state.replay_body is None:
            raise RuntimeError("Completed invitation idempotency record is missing its response body")
        return InvitationResponse.model_validate(state.replay_body)

    invitation = await invite_member(session, organization_id, context.user, payload)
    response = InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
    )
    await complete_idempotency(
        session,
        state.record,
        status_code=201,
        response_body=response.model_dump(mode="json"),
    )
    return response


@router.post("/invitations/accept", response_model=MembershipResponse)
async def accept_member_invitation(
    payload: AcceptInvitationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MembershipResponse:
    membership = await accept_invitation(session, user=user, raw_token=payload.token)
    return membership_response(membership, user)


@router.get("/{organization_id}/members", response_model=list[MembershipResponse])
async def list_members(
    organization_id: UUID,
    _: OrganizationContext = Depends(require_permission(Permission.MEMBERS_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> list[MembershipResponse]:
    rows = (
        await session.execute(
            select(OrganizationMembership, User)
            .join(User, User.id == OrganizationMembership.user_id)
            .where(OrganizationMembership.organization_id == organization_id)
            .order_by(OrganizationMembership.created_at, User.email)
        )
    ).all()
    return [membership_response(membership, user) for membership, user in rows]


@router.patch("/{organization_id}/members/{membership_id}", response_model=MembershipResponse)
async def change_member_role(
    organization_id: UUID,
    membership_id: UUID,
    payload: MembershipRoleUpdate,
    context: OrganizationContext = Depends(require_permission(Permission.MEMBERS_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> MembershipResponse:
    membership = await update_membership_role(
        session,
        organization_id=organization_id,
        membership_id=membership_id,
        actor=context.user,
        role=payload.role,
    )
    member = await session.get(User, membership.user_id)
    if member is None:
        raise RuntimeError("Membership references a missing user")
    return membership_response(membership, member)


@router.delete("/{organization_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    organization_id: UUID,
    membership_id: UUID,
    context: OrganizationContext = Depends(require_permission(Permission.MEMBERS_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await remove_membership(
        session,
        organization_id=organization_id,
        membership_id=membership_id,
        actor=context.user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
