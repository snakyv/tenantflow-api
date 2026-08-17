# ADR 0004 — Use durable workers for external background work

## Status
Accepted

## Context
Email and webhook delivery can be slow, fail transiently and require retries. FastAPI in-process background tasks are tied to an API process lifecycle.

## Decision
Use Celery with Redis for invitation emails and outbound webhooks. Jobs use late acknowledgement and explicit retry policies. API writes fail if a required job cannot be published, avoiding silent persistence of undeliverable work.

## Consequences
The API process remains focused on request latency while retryable work has a durable execution path. Redis availability becomes a dependency for write operations that require background delivery.
