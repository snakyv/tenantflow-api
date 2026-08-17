# ADR 0003 — PostgreSQL is the durable source of truth

## Status
Accepted

## Context
Redis is useful for coordination, throttling and task transport but creates unnecessary consistency problems if business records are split across databases.

## Decision
Users, organizations, memberships, projects, tasks, attachments, idempotency records, webhook delivery state, subscriptions and audit events live in PostgreSQL. Redis is used for rate limiting and Celery infrastructure.

## Consequences
Durable state has one transactional authority. Losing the local Redis cache/queue infrastructure does not redefine business ownership records.
