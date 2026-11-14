# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-15

First public release.

### Added

- Append-only, versioned record store on PostgreSQL with content-addressed documents in
  S3-compatible storage.
- Per-tenant SHA-256 hash-chained journal with checkpoints, and a verify endpoint that reports
  the first broken entry or document with the stored and recomputed hash.
- Point-in-time reads, version diffs, and constant-time latest reads.
- Tenant isolation with forced row-level security; a restricted application login.
- Demo tenants with a 24-hour lifetime, tamper and reset actions, and a nightly cleanup job.
- Clinician, auditor and admin roles; every content read is logged.
- React demo page with version comparison, the journal and verification.
- Benchmark suite with published results.
- Deployment on Vercel, Neon and Cloudflare R2, with a smoke test.
