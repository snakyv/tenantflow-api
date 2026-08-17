# ADR 0002 — Keep organization context explicit

## Status
Accepted

## Context
A user can belong to more than one organization. Encoding one permanent tenant in the access token makes tenant switching and membership revocation harder to reason about.

## Decision
JWT access tokens identify the user. Tenant routes include `organization_id`, membership is resolved server-side and organization-owned resources are always selected with both tenant and resource identifiers.

## Consequences
Cross-tenant access checks are auditable and testable. The additional membership lookup is accepted in exchange for clearer authorization semantics.
