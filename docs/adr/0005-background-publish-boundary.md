# ADR 0005: Background publish boundary

## Status

Accepted for the current modular-monolith scope.

## Context

Some HTTP use cases persist state and then need a durable Celery job. Invitation creation and outbound webhook delivery are the two current examples. PostgreSQL and Redis are independent systems, so a normal database transaction cannot atomically commit a database row and publish a Redis broker message.

Publishing only after the database transaction commits creates a failure window where durable state exists but its job was never published. Publishing before commit creates the opposite race: a fast worker may observe the broker message before the database row becomes visible.

## Decision

For the current project, broker publication happens before the request transaction exits.

- If broker publication fails, the exception aborts the request and PostgreSQL rolls back the corresponding state.
- Workers treat a briefly invisible row as retryable, covering the normal pre-commit visibility race.
- Worker handlers are idempotent and delivery state is persisted in PostgreSQL.
- The project does **not** claim exactly-once delivery.

## Consequences

This avoids silently committed work that was never queued. A later database rollback after a successful broker publish can create a harmless orphaned job; that job retries and then terminates without performing the business action because the referenced durable state does not exist.

The trade-off is intentionally documented rather than hidden behind an unreliable "distributed transaction" abstraction.

If TenantFlow grows to require stronger atomic guarantees, the next design step is a **transactional outbox** written in the same PostgreSQL transaction as the domain change, with a separate publisher that drains the outbox to Redis. That design is intentionally deferred until its extra operational complexity is justified.
