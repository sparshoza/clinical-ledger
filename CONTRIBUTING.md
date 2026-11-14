# Contributing

Issues and pull requests are welcome.

## Set up

Follow [Run it locally](README.md#run-it-locally) in the README. The test suite needs a second
database whose name ends in `_test`, set as `TEST_DATABASE_URL_OWNER` in `.env`; the tests drop
and recreate its schema.

## Before opening a pull request

```sh
uv run ruff check && uv run ruff format --check && uv run mypy
uv run pytest
npm --prefix web run lint && npm --prefix web run typecheck && npm --prefix web test
```

CI runs the same checks. New behaviour needs a test that fails without it.

## Rules the code keeps

- Ledger tables are append-only. Do not add code that updates or deletes versions, events,
  blobs or checkpoints; the database rejects it anyway.
- Every hash goes through `clinical_ledger.ledger.hashing`. Do not hash ad hoc.
- Queries on tenant data run inside `tenant_transaction`.
- Numbers in the docs come from a script in `bench/`, with the command and hardware beside them.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`,
`perf:`, `refactor:`, `test:`, `chore:`.
