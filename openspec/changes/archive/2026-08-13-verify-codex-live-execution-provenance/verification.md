# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual equivalent semantic OpenSpec review of completeness, correctness, and coherence against `model-routing`'s accepted "Routed Codex executor actually runs" scenario and this change's own added scenario (no `/opsx:verify` tool integration available in this environment), plus automated platform checks and a real, live Codex delegation as the acceptance evidence itself.
Automated-Checks-Evidence: automated-checks.json

## Reviewed behavior

- **Completeness**: all task-1 acceptance items are satisfied with real, non-fabricated evidence: 1.1 (live rate-limit re-check), 1.2 (real `route-codex` -> `dispatch_codex()` -> `run_codex()` delegation from this change's own managed task worktree), 1.3 (real `execution_id.value`, `model.source: selected`, truthful `reasoning_effort.source: unknown` persisted in `.claude/model-routing/verify-codex-live-execution-provenance.json`), 1.4 (no stronger surface found, so no correction to the parent change's evidence was needed), 1.5 (evidence recorded in this change's `pilot-evidence.md`). See that file for full command output and the route record.
- **Correctness**: the added `model-routing` scenario ("Live Codex delegation confirms real provenance capture") states GIVEN a real authenticated Codex CLI and a prepared routine/standard route, WHEN `run_codex()` launches it, THEN the participant carries a real bounded execution identifier from the live `--json` stream AND model/reasoning-effort reflect only what was actually confirmed. All four clauses hold against the actual observed run: `codex login status` confirmed real authentication; the route was the authored `R2` tier confirmed to `standard`; the persisted record's `execution_id` is a real, non-null `codex-thread` id (`019ff9c9-daac-7fb2-a730-e7b96343606f`) captured from the live event stream, not a simulated one; `model.source` stayed `selected` (not upgraded to `runtime-confirmed` without evidence) and `reasoning_effort.source` stayed truthfully `unknown`.
- **Coherence**: the added requirement/scenario is purely additive to the existing accepted `model-routing` spec's "Routed Codex executor actually runs" scenario (same GIVEN/WHEN/THEN shape, no requirement text changed, no conflict). No runtime/template code was changed by this acceptance run — the existing `run_codex()`/`--json` parsing path worked correctly against the real invocation, so design.md's "fix a real defect if found" contingency did not trigger. The dispatched executor's own nested self-dispatch attempt (recorded as a near-miss in `pilot-evidence.md`) is an artifact of this change's task being self-referential, not a defect in the path under test, and stays explicitly out of scope per design.md's non-goals.
- **No silent divergence**: `tasks.md` was updated in the same pass as the real evidence it now marks complete; no task was checked off ahead of, or without, the truthful evidence backing it.

## Automated checks

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 scripts/run_test_groups.py --all` — 541/541 tests, all 12 groups success (387.7s aggregate)
- `python3 template/scripts/openspec_lifecycle.py check` — OK
- `openspec validate verify-codex-live-execution-provenance --strict --no-interactive` — valid

## Real acceptance run (the change's actual deliverable)

See `pilot-evidence.md` for the full command, route record, and the nested-dispatch near-miss observed during the run. No runtime/template code changed; task 2.3's release step is therefore not required.
