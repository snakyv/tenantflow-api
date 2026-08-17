import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import token_fingerprint
from app.db.models import Invitation, Organization, OrganizationMembership, User
from app.modules.audit.service import record_audit
from app.modules.organizations.schemas import InviteMemberRequest, OrganizationCreate


async def create_organization(session: AsyncSession, user: User, payload: OrganizationCreate) -> Organization:
    if await session.scalar(select(Organization.id).where(Organization.slug == payload.slug)):
        raise ConflictError("ORGANIZATION_SLUG_EXISTS", "Organization slug is already in use")
    organization = Organization(name=payload.name.strip(), slug=payload.slug, created_by=user.id)
    session.add(organization)
    await session.flush()
    membership = OrganizationMembership(organization_id=organization.id, user_id=user.id, role="owner")
    session.add(membership)
    await record_audit(
        session,
        organization_id=organization.id,
        actor_id=user.id,
        action="organization.created",
        entity_type="organization",
        entity_id=organization.id,
    )
    return organization


async def invite_member(
    session: AsyncSession,
    organization_id: UUID,
    invited_by: User,
    payload: InviteMemberRequest,
) -> Invitation:
    normalized_email = payload.email.lower()
    existing_user_id = await session.scalar(select(User.id).where(User.email == normalized_email))
    if existing_user_id is not None:
        existing_membership = await session.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == existing_user_id,
            )
        )
        if existing_membership is not None:
            raise ConflictError("ALREADY_A_MEMBER", "This user already belongs to the organization")

    pending = await session.scalar(
        select(Invitation).where(
            Invitation.organization_id == organization_id,
            Invitation.email == normalized_email,
            Invitation.status == "pending",
        )
    )
    if pending is not None and pending.expires_at > datetime.now(UTC):
        raise ConflictError("INVITATION_ALREADY_PENDING", "A pending invitation already exists for this email")
    if pending is not None:
        pending.status = "expired"
        await session.flush()

    raw_token = secrets.token_urlsafe(32)
    invitation = Invitation(
        organization_id=organization_id,
        email=normalized_email,
        role=payload.role,
        token_hash=token_fingerprint(raw_token),
        status="pending",
        invited_by=invited_by.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=invited_by.id,
        action="member.invited",
        entity_type="invitation",
        entity_id=invitation.id,
        metadata={"email": normalized_email, "role": payload.role},
    )

    # Publishing is deliberately part of the request's use-case boundary. If the broker cannot
    # accept the durable job, the surrounding request transaction rolls back instead of silently
    # persisting an invitation that will never be delivered.
    from app.workers.tasks import send_invitation_task

    send_invitation_task.delay(str(invitation.id), raw_token)
    return invitation


async def accept_invitation(
    session: AsyncSession,
    *,
    user: User,
    raw_token: str,
) -> OrganizationMembership:
    fingerprint = token_fingerprint(raw_token)
    invitation = await session.scalar(
        select(Invitation).where(Invitation.token_hash == fingerprint).with_for_update()
    )
    if invitation is None:
        raise NotFoundError("INVITATION_NOT_FOUND", "Invitation was not found")
    if invitation.status != "pending":
        raise ConflictError("INVITATION_NOT_ACTIVE", "Invitation is no longer active")
    if invitation.expires_at <= datetime.now(UTC):
        invitation.status = "expired"
        await session.flush()
        raise ConflictError("INVITATION_EXPIRED", "Invitation has expired")
    if invitation.email != user.email.lower():
        raise ForbiddenError(
            code="INVITATION_EMAIL_MISMATCH",
            message="Invitation belongs to a different account",
        )

    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == invitation.organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role,
        )
        session.add(membership)
        await session.flush()

    invitation.status = "accepted"
    await record_audit(
        session,
        organization_id=invitation.organization_id,
        actor_id=user.id,
        action="member.joined",
        entity_type="organization_membership",
        entity_id=membership.id,
        metadata={"role": membership.role},
    )
    return membership


async def update_membership_role(
    session: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    actor: User,
    role: str,
) -> OrganizationMembership:
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise NotFoundError("MEMBERSHIP_NOT_FOUND", "Membership was not found")
    if membership.role == "owner":
        raise ForbiddenError(message="The organization owner role cannot be changed through this endpoint")
    old_role = membership.role
    membership.role = role
    await session.flush()
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor.id,
        action="member.role_changed",
        entity_type="organization_membership",
        entity_id=membership.id,
        metadata={"from": old_role, "to": role},
    )
    return membership


async def remove_membership(
    session: AsyncSession,
    *,
    organization_id: UUID,
    membership_id: UUID,
    actor: User,
) -> None:
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise NotFoundError("MEMBERSHIP_NOT_FOUND", "Membership was not found")
    if membership.role == "owner":
        raise ForbiddenError(message="The organization owner cannot be removed")
    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor.id,
        action="member.removed",
        entity_type="organization_membership",
        entity_id=membership.id,
        metadata={"user_id": str(membership.user_id), "role": membership.role},
    )
    await session.delete(membership)
