# 3. Serverless deployment on Vercel, Neon and R2

Status: accepted, November 2026

## Context

The demo has to stay online at no cost, on the same stack the code is written for: FastAPI,
PostgreSQL and S3-compatible storage. Traffic is light and bursty.

## Decision

- The FastAPI app runs as a Vercel Python function, found through a root `app.py`. Vercel builds
  the React page in the same deployment, and the function serves it.
- PostgreSQL is Neon, added through the Vercel marketplace, reached through its connection
  pooler. Migrations run from a developer machine with the owner login; the deployed app holds
  only the restricted `ledger_app` login, in `LEDGER_DATABASE_URL`.
- Documents are stored in Cloudflare R2 through the S3 API.
- A Vercel cron job calls the cleanup endpoint once a day to remove expired demo tenants.

## Consequences

- No servers to run and no monthly bill on these free tiers, within their quotas.
- Cold starts: the function and the database both sleep when idle, so the first request after a
  quiet spell takes seconds. The page shows a waking-up state instead of an error.
- Connections are opened per request, so the pooled endpoint matters.
- Verification fetches documents from R2 in parallel to stay well inside the function time
  limit.
- Hobby cron runs at most daily, which is fine for 24-hour demo tenants.

## Alternatives considered

- **A small always-on VM** (for example a free-tier cloud instance). No cold starts, but it needs
  patching and monitoring, and free tiers there expire.
- **Supabase for both database and storage.** One provider, but R2 has a larger free storage
  allowance and no egress fees.
- **Static front end on a separate host.** Works, but one deployment keeps the page and the API
  on the same origin, so no CORS configuration is needed.
