## Context

The importer already records provenance and the lifecycle already treats repository-local OpenSpec as canonical after materialization. The missing layer is resume-time enforcement: an old branch/PR can survive while the expected active change disappears, is replaced, or accepted current specs are edited without the canonical delta lifecycle being present.

## Decisions

### Preserve identity, not package immutability

The durable relationship is source Issue identity plus canonical change provenance. The original package is intentionally not re-applied on every resume because valid implementation discoveries may update repository-local planning.

The task checkout records that identity in a small root-level `.managed-task-state.json` marker. It contains only source Issue, target repository and change identity; the active or archived `.managed-task.json` remains the canonical OpenSpec provenance and the OpenSpec artifacts remain the sole canonical plan. The task-level marker lets the lifecycle recognize a managed task even when its expected canonical change is missing, so it can fail closed instead of treating the branch as quick work.

### Check at both resume and publication boundaries

Resume should detect invalid managed state before more implementation is added; finish/publication must check again because state may have changed in another session. Keep checks deterministic and based on repository/Git/OpenSpec evidence.

For compatibility, a pre-marker task with exactly one active canonical managed change can be resumed once and receives the marker. An archive is accepted only when its source/change identity matches and it retains completed task and semantic-verification evidence.

### Reuse existing completeness semantics

Task checkboxes, semantic verification receipt and archive state already encode the project's intended definition of done. Strengthen their association with managed source provenance rather than building an AI completeness scorer.

### Treat current-spec edits as explainable only through lifecycle evidence

Archived OpenSpec naturally produces current-spec changes, so current-spec edits are not inherently wrong. The defect is unexplained current-spec mutation with no matching canonical active/archive lineage.

## Risks / Trade-offs

- Historical managed work created before durable provenance may need a bounded recovery/migration path; fail closed rather than guessing ownership.
- Overly strict package byte matching would reject legitimate OpenSpec evolution, so identity and lifecycle evidence must be separated from transport hash equality.
