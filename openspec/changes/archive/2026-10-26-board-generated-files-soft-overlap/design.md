## Context

`_admission_conflicts` intersects the current task's claim candidates with each valid active sibling's owned claim paths; every common concrete path is a hard conflict unless acknowledged. The same function backs `hard_scope_conflicts`, used by `enforce_scope_gate` before validation and before publication. `scope_overlap_diagnostics` independently produces the advisory warning and is unchanged. `_platform_common.generated_files(root, commit)` reads and validates `[[generated_files]]` from the check configuration committed at `commit`, raising `TaskFreshnessError` on any irregularity.

## Decisions

- **Read the declaration at the observed `origin/<main>`.** The freshness classifier reads it at main for the same reason: a branch must not be able to declare its own conflict generated. The board already requires an observed `origin/<main>` for factual scope.
- **Exclude, do not acknowledge.** Generated paths are removed from the hard set before acknowledgment lookup; no acknowledgment record is written. They remain in the soft warning because that path is computed separately from all overlapping paths.
- **Fail closed.** An unobserved `origin/<main>` or a `TaskFreshnessError` from the declaration becomes the existing scope-gate-unavailable failure.
- **Read once per call.** The declaration is read once per `_admission_conflicts` call, only when there is at least one claim candidate.

## Risks

- Two tasks that hand-edit a generated file would not be serialized by the board. Mitigation: a generated file is by declaration rebuilt from sources by the queue and verified by its required check; a hand edit is overwritten and caught by that check.
