## Why

Stable release ships `template/` to downstream projects. Downstream archive (`template/scripts/openspec_lifecycle.py archive`) and Requirement lifecycle (`template/scripts/execute_requirement.py`) must run on the portable contract. Verified defects on current main:

- `openspec_lifecycle.archive_change` unconditionally executes `from pr_review_gate import managed_candidate` on every non-finalize archive. `pr_review_gate` imports `publication_queue` and `lifecycle_workers` at module level, so a downstream archive loads the whole coordinator stack before any contract check.
- `pr_review_gate.managed_candidate` evaluates `resolve_canonical_provenance(root)` before the `platform_version == "source"` test. In a downstream-shaped checkout with two active managed packages it raises `ManagedTaskError("multiple active managed OpenSpec packages make task identity ambiguous")` from a source-only question whose answer is already known to be "no".
- `execute_requirement._contribution_publication_supported` returns `False` for a source contract with `publish_mode`, `scm_provider` or `harness_mode` outside the supported combination, silently routing a source Requirement onto the legacy path.
- `openspec_lifecycle` carries `except ImportError` compatibility stubs (managed_task, independent_review) that silently substitute weaker behavior.

## What Changes

- Add one repository-owned selector in `_platform_common.py` that reads the committed contract and returns the lifecycle mode: portable for a downstream contract, coordinator for the supported source contract, and raises a named error for an unsupported source combination.
- `openspec_lifecycle.archive_change`, `pr_review_gate.managed_candidate` and `execute_requirement._contribution_publication_supported` consult the selector first; the coordinator stack is imported and evaluated only after the selector chose coordinator mode.
- Add downstream-shaped regression tests that run the entrypoints with coordinator modules unimportable and with ambiguous managed provenance.
- Report (not change) the existing `ImportError` compatibility stubs and the `publication_queue.enabled` bootstrap check as pre-existing fallbacks outside this outcome.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `completion-lifecycle`: archive and Requirement lifecycle select behavior from the committed contract before source-only logic.
- `lifecycle-workers`: the coordinator stack is source-only and never a mandatory downstream dependency.

## Impact

`template/scripts/_platform_common.py`, `template/scripts/openspec_lifecycle.py`, `template/scripts/pr_review_gate.py`, `template/scripts/execute_requirement.py`, `scripts/` shims where they mirror these files, new `tests/test_downstream_boundary.py`, and source/template parity of the touched files.

## Success Criteria

- Downstream-contract archive never imports `pr_review_gate`, `publication_queue` or `lifecycle_workers` and never resolves coordinator provenance.
- Ambiguous or malformed managed provenance cannot make `managed_candidate` raise under a downstream contract.
- A source contract with an unsupported combination raises a named error at selection; it never silently uses the portable path.
- Source coordinator behavior (supported combination) is unchanged and still covered by existing tests.

## Non-goals

Independent pre-release Requirements, stable tagging, fleet rollout, remote reviewer/TeamAI, removal of existing compatibility stubs and the `publication_queue.enabled` bootstrap check, unrelated cleanup.
