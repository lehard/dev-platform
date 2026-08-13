## Context

`adopt-gh-aw-process-automation` built and archived the full provenance data model and the Codex `--json`/`thread_id` capture path (`run_codex()` in `template/scripts/model_routing.py`), verified by unit tests using realistic captured event lines. What remains is exercising that exact path against a real, live `codex` CLI process end to end, which requires an unblocked Codex account.

## Goals

- Prove the already-implemented `run_codex()` provenance path against a real `codex exec --json` invocation, not a simulated stdout stream.
- Record truthful evidence: real `thread_id`, model source `selected` (or `runtime-confirmed` only if a stronger surface is discovered live), effort honestly `unknown` unless a real confirming surface is found.
- Keep the change bounded: one real run is sufficient acceptance evidence; this is verification, not new design.

## Non-goals

- Redesigning the provenance data model.
- Adding new model-routing behavior beyond what `adopt-gh-aw-process-automation` already shipped.
- Re-verifying the Claude leg (already closed with real evidence in the parent change).

## Decisions

### 1. Reuse the exact existing path

Run `python3 scripts/dogfood_task.py route-codex --profile routine --rationale "..." --evidence "..."` (or `standard`) from a real managed task worktree that already has a materialized `.managed-task.json` and this repo's `.dev-platform.toml` model-routing policy. Do not build a separate test harness for this -- the acceptance value is exercising the real production path.

### 2. Record what's actually observed

If the live run reveals a stronger runtime-confirmed surface for model or reasoning effort than the 2026-08-12 preflight found, update this change's evidence with that finding and correct `adopt-gh-aw-process-automation`'s pilot-evidence.md to note the surface exists (do not silently leave stale "unknown" documentation once truthfully confirmable evidence exists) -- but do not expand this change's own scope beyond recording that finding.

## Risks and mitigations

- **Account still rate-limited past 2026-08-18:** re-check before starting; if still blocked, report the blocker rather than fabricating a run.
- **Live run surfaces a real defect in the existing `--json` parser:** fix it as part of this bounded change (it's the same path being verified), with a regression test, rather than treating it as new scope creep.
