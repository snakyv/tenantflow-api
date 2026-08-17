"""Initial multi-tenant SaaS schema.

Revision ID: 20260817_0001
Revises:
Create Date: 2026-08-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB(astext_type=sa.Text())


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "organizations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.create_table(
        "organization_memberships",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
        sa.CheckConstraint("role IN ('owner','admin','member','viewer')", name="ck_organization_memberships_valid_membership_role"),
    )
    op.create_index("ix_membership_user_org", "organization_memberships", ["user_id", "organization_id"])

    op.create_table(
        "invitations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("invited_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
        sa.CheckConstraint("role IN ('admin','member','viewer')", name="ck_invitations_valid_invitation_role"),
        sa.CheckConstraint("status IN ('pending','accepted','revoked','expired')", name="ck_invitations_valid_invitation_status"),
    )
    op.create_index(
        "uq_invitation_pending_org_email",
        "invitations",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "projects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("organization_id", "name", name="uq_project_org_name"),
        sa.UniqueConstraint("organization_id", "id", name="uq_project_org_id"),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_projects_valid_project_status"),
    )
    op.create_index("ix_project_org_created", "projects", ["organization_id", "created_at"])

    op.create_table(
        "tasks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("assignee_id", UUID, sa.ForeignKey("users.id")),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("organization_id", "id", name="uq_task_org_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_task_project_same_org",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("status IN ('todo','in_progress','done','cancelled')", name="ck_tasks_valid_task_status"),
        sa.CheckConstraint("priority IN ('low','medium','high','urgent')", name="ck_tasks_valid_task_priority"),
    )
    op.create_index("ix_task_org_project_created", "tasks", ["organization_id", "project_id", "created_at"])
    op.create_index("ix_task_org_assignee_status", "tasks", ["organization_id", "assignee_id", "status"])

    op.create_table(
        "attachments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID),
        sa.Column("task_id", UUID),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            name="fk_attachment_project_same_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "task_id"],
            ["tasks.organization_id", "tasks.id"],
            name="fk_attachment_task_same_org",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "(project_id IS NOT NULL) <> (task_id IS NOT NULL)",
            name="ck_attachments_attachment_exactly_one_parent",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_attachments_attachment_positive_size"),
        sa.UniqueConstraint("object_key", name="uq_attachments_object_key"),
    )
    op.create_index("ix_attachment_org_object", "attachments", ["organization_id", "object_key"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", UUID, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_user_expires", "refresh_tokens", ["user_id", "expires_at"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(120), nullable=False),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
        sa.CheckConstraint("status IN ('processing','completed','failed')", name="ck_idempotency_records_valid_idempotency_status"),
    )
    op.create_index("ix_idempotency_expires", "idempotency_records", ["expires_at"])

    op.create_table(
        "webhook_endpoints",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("signing_secret_hash", sa.String(64), nullable=False),
        sa.Column("signing_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("events", JSON, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_webhook_endpoint_org_active", "webhook_endpoints", ["organization_id", "is_active"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("endpoint_id", UUID, sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("last_error", sa.Text()),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("event_id", "endpoint_id", name="uq_delivery_event_endpoint"),
        sa.CheckConstraint("state IN ('pending','delivered','retrying','dead')", name="ck_webhook_deliveries_valid_delivery_state"),
    )
    op.create_index("ix_delivery_state_next_retry", "webhook_deliveries", ["state", "next_retry_at"])

    op.create_table(
        "subscriptions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("organization_id", name="uq_subscription_organization"),
        sa.UniqueConstraint("stripe_customer_id", name="uq_subscriptions_stripe_customer_id"),
        sa.UniqueConstraint("stripe_subscription_id", name="uq_subscriptions_stripe_subscription_id"),
        sa.CheckConstraint("plan IN ('free','pro','business')", name="ck_subscriptions_valid_subscription_plan"),
        sa.CheckConstraint("status IN ('inactive','trialing','active','past_due','cancelled')", name="ck_subscriptions_valid_subscription_status"),
    )

    op.create_table(
        "stripe_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("stripe_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("stripe_event_id", name="uq_stripe_events_stripe_event_id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(160), nullable=False),
        sa.Column("entity_type", sa.String(120), nullable=False),
        sa.Column("entity_id", UUID),
        sa.Column("metadata", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_org_created", "audit_logs", ["organization_id", "created_at"])


def downgrade() -> None:
    for table in [
        "audit_logs",
        "stripe_events",
        "subscriptions",
        "webhook_deliveries",
        "webhook_endpoints",
        "idempotency_records",
        "refresh_tokens",
        "attachments",
        "tasks",
        "projects",
        "invitations",
        "organization_memberships",
        "organizations",
        "users",
    ]:
        op.drop_table(table)
