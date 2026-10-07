## Context

Current code (all under `template/scripts/`, rendered downstream; `scripts/*` in this repository are shims or mirrors):

- `openspec_lifecycle.py:archive_change` non-finalize branch runs `from pr_review_gate import managed_candidate` and calls it for every project, downstream included.
- `pr_review_gate.py` imports `lifecycle_workers as workers` and `publication_queue as queue` at module top; `managed_candidate(root)` computes `resolve_canonical_provenance(root)` first and only then tests `config.get("platform_version") == "source" and queue.enabled(root)`.
- `publication_queue.py:enabled` checks `platform_version == "source"` first, then `origin/main:WORKFLOW`; it is the only real source test and lives inside the stack downstream must not depend on.
- `finish_task.py` (~line 904) and `project_publish.py` (~lines 525, 648) already test `platform_version == "source"` before importing the coordinator; `openspec_lifecycle._candidate_context` also tests it first. These are the established pattern; archive and `managed_candidate` are the exceptions.
- `execute_requirement.py:_contribution_publication_supported` returns `False` for source + `publish_mode != pr` / `scm_provider != github` / `harness_mode != platform` (silent switch to the legacy per-child path), else delegates to `publication_queue.enabled`.
- Verified experiment: copying `template/scripts` with `platform_version = "1.0.0"`, `pr_review_gate` imports (loading the coordinator stack) and `managed_candidate` raises `ManagedTaskError: multiple active managed OpenSpec packages make task identity ambiguous` when two `.managed-task.json` packages exist.
- Existing fixtures: `tests/test_openspec_lifecycle.py:make_standard_repo` copies `template/scripts` into a git repo with `platform_version = "customer"`; `tests/test_requirement_execution.py:test_downstream_multi_child_uses_existing_supervisor_path` mocks a downstream config.

## Goals

- Contract first: behavior is selected from committed `.dev-platform.toml` before any coordinator module is imported or evaluated.
- Source-only logic is never a mandatory downstream dependency.
- Unsupported combinations fail explicitly.

## Decisions

1. One selector, `_platform_common.lifecycle_mode(config) -> "portable" | "coordinator"` (no side effects, no git, no network). `platform_version != "source"` returns portable. `platform_version == "source"` requires `harness_mode == platform`, `publish_mode == pr`, `scm_provider == github` and otherwise raises `PlatformConfigError` naming the offending key and value. Missing optional keys use the existing config schema reader values already applied by `read_platform_config`; the selector adds no new defaults and a non-string/absent `platform_version` raises. Rejected: per-call-site ad hoc checks (current drift) and a flag file.
2. `openspec_lifecycle.archive_change` calls the selector before the review branch; the `from pr_review_gate import managed_candidate` import and call happen only in coordinator mode. Portable mode runs `ensure_review_evidence` and the select-checks path exactly as today for non-coordinator-managed work.
3. `pr_review_gate.managed_candidate` reorders: selector first; portable returns `False` without provenance resolution; coordinator mode then keeps the current provenance + `queue.enabled` logic. Provenance errors in coordinator mode still propagate (no swallowing).
4. `execute_requirement._contribution_publication_supported` uses the selector: portable returns `False` (legitimate downstream contract), coordinator proceeds to `publication_queue.enabled`; an unsupported source combination now raises instead of returning `False`.
5. `pr_review_gate` defers worker and queue imports to coordinator operations, including lazy resolution of its injectable queue adapter. `finish_task.main`, `project_publish.main` and `project_publish.publish_pr` select lifecycle mode before publication work; an explicit downstream developer handoff is rejected before loading coordinator modules. No coordinator-only module is imported at module top by any downstream-reachable entrypoint. A regression test with an import blocker enforces this for `openspec_lifecycle`, `execute_requirement` and `requirement_terminal`.
6. Pre-existing fallbacks found and reported, not changed here: the `except ImportError` stubs in `openspec_lifecycle.py` (managed_task, independent_review compatibility) and the `publication_queue.enabled` bootstrap (`origin/main:WORKFLOW` absent returns False). They are outside this outcome and need a user decision.

## Risks

- Failing explicitly for a source contract with an unsupported combination could break an internal test or script that sets `platform_version = "source"` with another provider. Mitigation: grep tests and scripts for such configs before implementation; adjust fixtures that were accidentally relying on the silent switch.
- Reordering `managed_candidate` must not change coordinator-mode behavior; existing `tests/test_pr_review_gate.py` and `tests/test_openspec_lifecycle.py` guard this.
- Source/template parity: `scripts/` mirrors must stay identical.

## Verification

- New `tests/test_downstream_boundary.py` builds a downstream-shaped checkout (copy of `template/scripts`, `platform_version = "1.0.0"`, `harness_mode = "platform"`) and, in a subprocess with an import blocker for `pr_review_gate`, `publication_queue`, `lifecycle_workers`, runs `scripts/openspec_lifecycle.py archive` through a fake `openspec` binary (reuse `make_standard_repo` style).
- Same fixture with two active managed packages: `managed_candidate` returns `False`, no `ManagedTaskError`.
- Selector unit cases: downstream, supported source, source+gitlab, source+direct, source+project harness, missing `platform_version`.
- `_contribution_publication_supported` portable returns `False`; unsupported source raises.
- Existing source tests (`tests/test_pr_review_gate.py`, `tests/test_openspec_lifecycle.py`, `tests/test_requirement_execution.py`, `tests/test_publication_queue.py`) pass unchanged; `python3 scripts/run_test_groups.py --all`.
- Record actual commands and results in verification.md; full release validation and real BR-391 dogfood remain parent release prerequisites.
