# 2. Tenant isolation with PostgreSQL row-level security

Status: accepted, November 2026

## Context

Every visitor to the demo gets a private ledger they can tamper with, and nothing one visitor
does may show up for another. A future paying customer would need the same guarantee. Filtering
by tenant in every query works until one query forgets the filter.

## Decision

Every tenant-scoped table carries `tenant_id`, with row-level security enabled and forced. The
policy compares `tenant_id` to `current_setting('app.tenant_id', true)`, which the application
sets with `set_config(..., true)` at the start of each transaction, so it lasts for that
transaction only. Connections run in autocommit mode, so a query outside a tenant transaction
sees no tenant rows at all.

The application connects as `ledger_app`, which owns nothing and cannot alter policies.
Maintenance (deleting expired tenants) runs through a `SECURITY DEFINER` function owned by the
migration's login. The policies have a maintenance bypass, but it applies only when the current
user is not `ledger_app`, so the application cannot switch it on for itself.

## Consequences

- A query with a missing `WHERE tenant_id = ...` returns nothing from other tenants instead of
  leaking them.
- Every code path that reads tenant data must run inside the tenant transaction; tests run as
  `ledger_app` so a path that forgets fails visibly.
- Shared data (seed documents in `blobs`, the demo actors) lives in tables without tenant rows,
  so it is stored once.

## Alternatives considered

- **A schema or database per tenant.** Strong isolation, but thousands of short-lived demo
  tenants would mean thousands of schemas to create and drop.
- **Application-level filtering only.** Cheapest, and one forgotten filter away from a leak.
