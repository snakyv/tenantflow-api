# ADR 0001 — Use a modular monolith

## Status
Accepted

## Context
TenantFlow needs clear domain boundaries but is a single-team portfolio backend. Networked microservices would add distributed transactions, deployment surfaces and failure modes without solving an actual scale or ownership problem.

## Decision
Use one deployable FastAPI application with modules for authentication, organizations, projects, tasks, files, webhooks, billing and audit. Durable workers are separate processes because they have a different execution lifecycle, not because the domain is artificially split.

## Consequences
Domain boundaries remain visible while local development, transactions and debugging stay simple. A future module can be extracted only when independent scale or ownership creates a real reason.
