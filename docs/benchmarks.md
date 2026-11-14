# Benchmarks

Every number on this page comes from the scripts in `bench/`. They run against one
tenant holding 2,000,000 journal entries over 500,000 versions
of 48,993 records, all in a single hash chain. Measured 2026-11-14.

![Median latency of reading a record's latest version](img/latest-read-latency.svg)

Reading the latest version costs the same whether a record has 1 version or 10,000:
the head of each record is kept in its own row, so a read never scans history.

## Writes

Adding a version: store the content, insert the version, move the record head and
append a journal entry with its hash, in one transaction. Milliseconds.

| Writers | p50 | p95 | p99 |
| --- | ---: | ---: | ---: |
| 1 writer | 1.36 | 2.47 | 4.36 |
| 8 writers, same tenant | 10.57 | 19.84 | 29.55 |

Entries in one tenant's journal are written one at a time, because each entry carries
the hash of the one before it. Eight writers on the same tenant therefore queue: each
waits for the others, which is the cost of a single unbroken chain. Writers in
different tenants do not wait for each other.

## Reads

A full read fetches the content, checks it against its hash, and appends a
`record.read` entry to the journal. A head lookup is the index query alone.
Milliseconds.

| Versions on the record | Head lookup p50 | Full read p50 | Full read p95 | 8 readers p50 | 8 readers p95 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.23 | 0.90 | 2.04 | 5.24 | 7.84 |
| 100 | 0.23 | 0.94 | 1.79 | 6.59 | 8.29 |
| 10,000 | 0.17 | 0.86 | 1.64 | 5.44 | 9.93 |

Reading a record as it stood at a past moment (the version in force at that time):

| Read | p50 | p95 | p99 |
| --- | ---: | ---: | ---: |
| As of a past time | 1.21 | 2.48 | 8.76 |

## Verification

Verifying recomputes every entry's hash from its fields and the previous hash, and
rehashes every stored document. Starting from the latest checkpoint (written every
1,000 entries) checks only the entries after it.

| From | Entries checked | Documents checked | Seconds | Entries per second |
| --- | ---: | ---: | ---: | ---: |
| The first entry | 2,018,884 | 504,196 | 107.015 | 18,865 |
| The latest checkpoint | 884 | 0 | 0.097 | 9,134 |

The full run checks 18,884 more entries than were loaded: the measurements above
append journal entries of their own, and those are verified too.

Both runs reported the chain intact.

## Starting a demo

Creating a demo tenant: 75 records, their versions and a fresh hash chain,
inserted in one transaction. Each run opens its own connection, as a serverless
request does. Milliseconds.

| Database | Runs | p50 with connect | p95 with connect | p50 insert only |
| --- | ---: | ---: | ---: | ---: |
| local | 20 | 70.51 | 197.93 | 41.19 |

## Setup

- Machine: 12th Gen Intel(R) Core(TM) i7-12700H, 14 cores (20 threads), 15.7 GB RAM, Windows 11
- PostgreSQL 16.15 on the same machine, Python 3.12.3
- Document storage: in process, so object storage network time is not counted.
  The deployed demo stores documents in Cloudflare R2; expect its reads to add
  that round trip.
- Load: 191.4 seconds to compute and bulk-copy the data set
- Each timing discards a warm-up of 100 operations, then takes 2,000.
- Concurrent runs use one connection per thread.

PostgreSQL settings changed from the defaults:

| Setting | Value |
| --- | --- |
| `max_connections` | 100 |
| `max_wal_size` | 1024 MB |
| `min_wal_size` | 80 MB |
| `shared_buffers` | 128 MB |

## Reproduce

```sh
python -m bench.load            # creates clinical_ledger_bench and loads it
python -m bench.run             # writes bench/results/<timestamp>.json
python -m bench.tenant_create   # times 20 demo tenant creations
python -m bench.report          # rewrites this page and its chart
```

`bench.load` reads `DATABASE_URL_OWNER` and drops and recreates the
`clinical_ledger_bench` database next to it. `bench.run` connects as `ledger_app`,
the same restricted login the application uses.
