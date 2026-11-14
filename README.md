# Clinical Ledger

[![CI](https://github.com/sparshoza/clinical-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/sparshoza/clinical-ledger/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
[![Live demo](https://img.shields.io/badge/demo-live-brightgreen.svg)](https://clinical-ledger-weld.vercel.app)

A clinical record store where nothing is overwritten and any tampering is caught. Every change
to a record is a new version, every action is a journal entry chained to the one before it by
SHA-256, and a verify call walks the chain to find the first entry that no longer adds up.

**Live demo: [clinical-ledger-weld.vercel.app](https://clinical-ledger-weld.vercel.app)**.
Each visitor gets a private ledger with 75 synthetic records. Edit one, tamper with the journal
or a stored file, then verify and watch the break get caught. All data is synthetic, generated
with [Synthea](https://synthetichealth.github.io/synthea/). No real patient data is used anywhere.

## What it shows

- **Append-only versions.** A change inserts a new version row and moves the record's head
  pointer. Database triggers reject `UPDATE` and `DELETE` on versions, events, blobs and
  checkpoints, and the application's login has no right to bypass them.
- **A hash-chained journal.** Each entry's hash covers its fields and the previous entry's hash,
  so editing any entry breaks every link after it. Checkpoints every 1,000 entries let
  verification start from a known-good point.
- **Content-addressed storage.** Documents live in S3-compatible storage under their own
  SHA-256, and every read checks the bytes against that hash before returning them.
- **Constant-time latest reads and point-in-time reads.** The latest version is one indexed
  lookup no matter how long the history is. Any record can be read as it stood at a past moment,
  and any two versions can be diffed.
- **Tenant isolation in the database.** PostgreSQL row-level security scopes every query to the
  caller's tenant, so a missing filter in application code still cannot return another tenant's
  rows.
- **Roles and access logging.** Clinicians read and write records, auditors see the journal but
  not content, admins can do both. Every read of record content is itself a journal entry.

Architecture, data model and request flow: [docs/architecture.md](docs/architecture.md).
Decisions and the alternatives considered: [docs/adr/](docs/adr/).

## Benchmarks

One tenant holding 2,000,000 journal entries over 500,000 versions, PostgreSQL 16 on a laptop
(Intel i7-12700H), documents stored in process. Medians in milliseconds unless noted.

| Operation | p50 | p95 |
| --- | ---: | ---: |
| Add a version (1 writer) | 1.36 | 2.47 |
| Read the latest version, record with 1 version | 0.90 | 2.04 |
| Read the latest version, record with 10,000 versions | 0.86 | 1.64 |
| Read as of a past time | 1.21 | 2.48 |
| Verify the whole chain | 18,865 entries/s | |
| Verify from the latest checkpoint | 0.10 s | |

Method, hardware, settings, concurrency results and the commands to reproduce them:
[docs/benchmarks.md](docs/benchmarks.md). The live demo adds network time to every call.

## Run it locally

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 and PostgreSQL 16.

```sh
cp .env.example .env              # fill in the PostgreSQL logins and secrets
createdb clinical_ledger          # and clinical_ledger_test for the test suite
uv sync
uv run alembic upgrade head       # creates the schema and the restricted ledger_app login
S3_BACKEND=memory uv run uvicorn clinical_ledger.main:app --reload
npm --prefix web install
npm --prefix web run dev          # http://localhost:5173
```

With `S3_BACKEND=memory` documents stay in process and the seed loads at startup, so no object
storage is needed. API reference: http://localhost:8000/api/docs.

## Tests

```sh
uv run pytest                     # unit, database and API tests (needs TEST_DATABASE_URL_OWNER)
uv run ruff check && uv run mypy
npm --prefix web test             # component tests
npm --prefix web run e2e          # browser tests against a local API and web server
```

## Limitations

- Synthetic data only. This is a demonstration, not a certified or HIPAA-compliant system.
- Writes in one tenant are serialized, because each journal entry needs the previous entry's
  hash. Eight writers on one tenant queue behind each other (see the benchmarks); writers in
  different tenants do not.
- The hosted demo runs in a single region on free tiers, and its database sleeps when idle, so
  the first request after a quiet spell is slow.
- Demo ledgers expire after 24 hours and are removed by a nightly job.

## License

[MIT](LICENSE). Synthetic patient data generated with Synthea (Apache 2.0); see
[fixtures/synthea/NOTICE](fixtures/synthea/NOTICE).
