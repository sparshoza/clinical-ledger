# 1. A hash-chained event log for tamper evidence

Status: accepted, November 2026

## Context

A clinical record store has to show that history has not been rewritten. Database permissions
stop an honest application from editing rows, but they do not prove to an auditor that nobody
with owner access did. The proof needs to be checkable from the data itself.

## Decision

Every action (record created, version added, record read, verification run) appends one entry
to a per-tenant journal. Each entry stores the previous entry's hash and its own hash, computed
with SHA-256 over the previous hash and a canonical JSON encoding of its fields. Documents are
stored under their own SHA-256, and version rows reference that hash.

A checkpoint row records the entry number and hash every 1,000 entries, so verification can
start from a known point instead of the first entry.

## Consequences

- Changing any entry, or any stored document, is detectable, and verification names the first
  entry or document that fails.
- Appends in one tenant are serialized by an advisory lock, because each entry needs its
  predecessor's hash. Throughput per tenant is bounded; different tenants do not contend.
- Hashing has to be deterministic across a database round trip, so canonical JSON rejects
  floats and fixes the timestamp format.
- Detection is not prevention: someone with owner access can still rewrite the whole chain from
  a point onward. Publishing checkpoint hashes outside the database would close that gap.

## Alternatives considered

- **Database audit triggers only.** Simple, but an owner can edit the audit table too, and there
  is nothing to verify.
- **A Merkle tree over all entries.** Gives compact proofs for single entries, but the demo needs
  "find the first break", which a linear chain answers directly.
- **A blockchain or external ledger service.** Adds consensus and cost the problem does not need.
