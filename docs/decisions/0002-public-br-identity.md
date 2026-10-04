# DEC-0002: Public BR identity with private technical lineage

- **Status:** Current
- **Scope:** Managed intake and public provenance; dependent publication formatting
- **Decision date:** 2026-10-04
- **Authored against revision:** `ff69a8d5f115d3815b9d333c4bb40fd72689dca4`
- **Supersedes:** None
- **Superseded by:** None

## Accepted current decision

The approved privacy boundary permits public `BR-N` and `BR-N/Tn` tokens derived
from the parent Requirement number and a stable child ordinal. The parent
number is not secret. Exact technical provenance remains an opaque private
lineage handle. Canonical repository references and Requirement content remain
private. Validate the entire token before publishing it; this permission does
not extend to arbitrary metadata, titles, URLs or repository names.

The `stable-br-work-identity` proposal and `managed-task-intake` privacy delta
in the [OpenSpec contract](../../openspec/) record the approved scope; use the
canonical active or archived package for that change. Private exact mappings continue to live in their
own Issue records. No second identity service is introduced.

## Rejected and deferred alternatives

Publishing exact Backlog references or Requirement prose is rejected because
readable work tracking does not require exposing those private facts. Keeping
all work identity opaque is rejected for this approved iteration because it
prevents readable parent/child association. Native Issue-number synchronization,
a separate identity registry, owner labels and a shared product taxonomy are
outside the approved boundary. Branch and PR formatting is deferred to the
dependent child; this decision does not implement that propagation.

## Revisit triggers

Re-evaluate if parent numbers become sensitive, if identities must distinguish
multiple Backlog namespaces in the same public project, or if concrete evidence
shows BR tokens expose private content beyond the approved number and ordinal.
Cross-host allocation conflicts may justify an atomic storage adapter, but do
not authorize a registry or wider public identity. A new managed change must
approve any widened boundary before implementation.
