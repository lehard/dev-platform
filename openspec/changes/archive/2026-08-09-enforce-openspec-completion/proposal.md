# Proposal: Enforce OpenSpec completion lifecycle

## Why

The platform already requires no-silent-divergence and semantic OpenSpec verification before archive, but completion is still behavioral rather than mechanically guarded. `finish_task.py` can publish finished implementation while an OpenSpec change remains active, and the repository already contains completed/stale active changes. This weakens `openspec/specs/` as the accepted source of truth and makes humans/agents remember the last lifecycle steps.

## What changes

- Add a platform-managed OpenSpec lifecycle gate that detects completed-but-active changes.
- Add one supported archive entrypoint that requires completed tasks and a recorded successful semantic OpenSpec verification result and method before invoking OpenSpec archive.
- Prefer `/opsx:verify` where available while allowing the documented equivalent completeness/correctness/coherence review in agent environments without that command surface.
- Make `finish_task.py` refuse publication while a completed OpenSpec change is still active.
- Run lifecycle hygiene and strict OpenSpec structural validation in generated project CI.
- Update agent/OpenSpec guidance so agents own `verify -> archive -> publish` without routine human reminders.
- Reconcile and archive historical dev-platform changes that are already complete or superseded, preserving their verification evidence and accepted behavior.

## Non-goals

- Do not replace OpenSpec's own validation/archive semantics.
- Do not pretend that Python performs semantic verification; it only checks the recorded verification receipt and method before archive.
- Do not auto-archive incomplete changes or silently accept failed verification.
- Do not add a second backlog or workflow engine.

## Affected areas

- `template/scripts/`
- generated `AGENTS.md` and OpenSpec config
- generated check configuration / CI contract
- dev-platform OpenSpec lifecycle and archive hygiene
