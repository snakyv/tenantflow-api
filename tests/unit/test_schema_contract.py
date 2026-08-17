from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db.base import Base
from app.db import models  # noqa: F401


EXPECTED_TABLES = {
    "users",
    "organizations",
    "organization_memberships",
    "invitations",
    "projects",
    "tasks",
    "attachments",
    "refresh_tokens",
    "idempotency_records",
    "webhook_endpoints",
    "webhook_deliveries",
    "subscriptions",
    "stripe_events",
    "audit_logs",
}

TENANT_TABLES = {
    "organization_memberships",
    "invitations",
    "projects",
    "tasks",
    "attachments",
    "idempotency_records",
    "webhook_endpoints",
    "subscriptions",
    "audit_logs",
}


def test_expected_tables_are_present() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_tenant_owned_tables_have_organization_id() -> None:
    for table_name in TENANT_TABLES:
        assert "organization_id" in Base.metadata.tables[table_name].columns


def test_all_models_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in ddl
