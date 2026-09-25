## Boundary and identity

The private Backlog Issue retains the exact Issue identity and an assigned random lineage handle. Public committed managed provenance and derived check/integration receipts carry only that handle. The local ignored task state retains exact identity for authorization and normal lifecycle operation. A recovery from an Issue fetches that private Issue through existing credentials, reads the handle, and compares it with public archived provenance. Missing, ambiguous, or contradictory handles fail closed. The handle must not encode a repository name or Issue number.

Current archived records are migrated by mapping each exact private Issue to one handle in that same private Issue before redacting public records. The migration preserves command outcomes, task completion, verification method and materialized spec. Sanitized archive records indicate that identity fields were redacted after the original verification, so they do not pretend to be byte-for-byte original command output. The Git history retains originals.

Shared Requirement integration keeps its exact manifest in ignored local execution state. Its public branch name, child and binding commit messages, committed manifest, and PR body use private-Issue handles. The protected publisher receives the exact manifest only in its process environment, checks the public projection against private Issue mappings, and verifies parent/child links before a push. Public process-evidence comments use the same handles. This keeps future shared deliveries usable under the source guard.

## Public checks and external cleanup

A deterministic guard checks tracked public candidate files and public report text for supported private Issue reference forms. It uses the configured private Backlog identity where available and fails closed on unknown private-looking managed lineage; synthetic fixtures and known public references are handled explicitly. The guard must run before PR publication and on protected CI. It does not claim to detect arbitrary prose from private tasks.

The external audit inventories public Issues, Actions run logs and artifacts using bounded GitHub API reads. Confirmed affected old runs are deleted with their artifacts, and editable Issue text is sanitized. Results and limitations are recorded privately in the Requirement; immutable Git history is not rewritten.

## Safety and rollout

Migrate existing public records and install the guard in one candidate so the candidate does not self-block. Keep private mapping writes idempotent and verify read-back before redaction. Validate exact source recovery, fresh task archive, current-tree scan, protected CI, and live public surface audit. Preserve all existing OpenSpec and publication gates.
