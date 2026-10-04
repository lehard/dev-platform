## Context
Canonical parent references and the Requirement children block already own linkage. Public private-lineage handles own exact technical provenance. The user explicitly approved revealing only the parent number through BR-N and the child ordinal through BR-N/Tn.

## Decisions
Use a shared dependency-light identity helper derived from existing parent links. Store stable child presentation assignments in existing Requirement/child records, never a separate identity/status registry. Allocate monotonically without reusing removed assignments; serialize local mutation with existing locking primitives and read back both directions; stale/conflicting/duplicate ordinals fail closed. Legacy children receive identities on normal linking/materialization/import; repeated recovery preserves assigned ordinals. Keep the canonical standalone Requirement reference unchanged in private Issue text for parsers.

Expose a private-safe identity field in imported provenance and necessary integration receipts while retaining opaque source handles. Public code/docs/tests use synthetic repository names. Do not include private Requirement prose in public artifacts. Assignee uses GitHub; taxonomy remains project-owned.

## Risks and Mitigations
Concurrent or interrupted linking could duplicate/reassign children: bound allocation to existing parent/child records, check duplicates and read back on retry rather than guessing. Old provenance must remain readable: new identity data is additive and optional for legacy records. Copier upgrades must carry shared helper files without overwriting project-owned agent/taxonomy files. Replacing privacy rules broadly could leak metadata: allow only validated BR tokens and keep exact Backlog-ref guards active.

## Verification
Test two-child allocation, retries, removed/reordered children, conflict refusal, legacy import, private-safe provenance, new-project rendering and upgrade inclusion. Review the privacy contract semantically before archive.

### Allocation transaction
Persist `Work identity: BR-N` on the parent and `Work identity: BR-N/Tn` on the child. Retain immutable `br-child` reservation comments in the parent body even when checklist links are removed. Reconcile those reservations with all child Issue bodies in the same Backlog repository (including closed Issues) before allocation. Write the child's claim first, then the parent reservation/link, and read both directions and sibling claims back. A same-operator host-local advisory lock serializes cooperating writers without durable identity state. GitHub Issue edits have no compare-and-swap guarantee: cross-host identity collisions or lost identity claims observable in readback fail closed; repair conflicting reservations explicitly, never renumber silently. GitHub body replacement is not atomic with the freshness read: an unrelated manual prose edit wholly overwritten between that read and the replacement is not observable and cannot be guaranteed by this protocol. Avoid overlapping manual body edits during linking; an observed pre-write body change stops the operation, and readback checks the expected bodies as well as assignments. This limitation also applies to the existing checklist-linking body update; no compare-and-swap support is claimed. Removed checklist links do not remove reservations. Missing both copies after destructive manual deletion cannot be reconstructed and is outside supported edits.

### Lifecycle recovery
Normal start/resume reconciles canonical Issue claims before refreshing task state and bounded context. Active provenance receives the additive safe identity without overwriting authored artifacts; an archived provenance is checked but not rewritten. GitHub pagination is explicitly slurped and flattened before sibling validation.

### Historical revision compatibility
Append the safe identity field without trimming any pre-existing body bytes. For legacy raw-body revision evidence, also compare the exact original body obtained by removing only the deterministic appended identity suffix. Keep title and all authored prose in the hash so actual scope edits still require explicit acknowledgement. Final readback re-fetches every reserved or allocated child directly, including claims removed from the parent-filtered API scan.

### Recovery completeness
Requirement start establishes and validates its parent BR field before creating pre-authoring state. Final allocation readback validates both the identity and the unique canonical parent line on every allocated child, not just the currently linked child. Missing sibling claims require explicit inspection/recovery; parent reservations alone are not proof of current bidirectional linkage.

### Shared parent mutation lock
Requirement creation and start identity recovery use the same per-parent advisory lock as child linking. Recovery validates its supplied body against a fresh read inside that lock and retains exact-body readback. A cooperating link cannot complete between the recovery freshness check and replacement; an earlier completed link makes a stale recovery refuse rather than replace its checklist or reservations.
