# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-15

### Added

- A home page that explains what the ledger does, beside the visitor's own live ledger with a
  working Verify button. The console moves to `/demo`.
- Limits that keep the shared demo available: 10 new demo ledgers per visitor address an hour
  (addresses kept only as a keyed hash, for a day) and 300 new versions per ledger.

### Changed

- New slate and cobalt colour scheme. Red stays reserved for entries that do not reconcile.
- Storage errors from the object store now return `503` problem responses, and any unexpected
  error returns a problem response instead of plain text. One storage client is shared per
  process, with connect and read timeouts.

### Fixed

- Every "Add a version" in the demo now changes the record; some demo edits used to repeat a
  value already present and produce an empty comparison.
- A returning visitor whose session had expired could start several new ledgers at once.
- The nightly cleanup now deletes tampered file copies along with expired demo ledgers.

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
