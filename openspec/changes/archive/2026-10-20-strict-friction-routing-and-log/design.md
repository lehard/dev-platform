## Context

`template/scripts/agent_friction.py` records events locally (`.claude/agent-friction.jsonl`), routes them to GitHub (`route_event`/`route_pending`) and drives retrospectives/checkpoints. `route_event` already converts a `RuntimeError` into a retained `pending` route with a sanitized `detail`, and `agent_doctor`/`finish_task` call `route-pending` as a non-blocking retry that prints warnings. Coordinator durable evidence already uses an explicit tolerance context (`tolerate_durable_gap`) that is entered only where a gap is reported or explicitly accepted.

## Goals / Non-Goals

Goals: no silent destination substitution; configuration read errors surface; a malformed or unreadable log is a named error; event identity never depends on line position.

Non-goals: dedupe by root cause, auto-close, quiet start/doctor/advance, coordinator event content, triage workflow, moving historical issues, changing high-signal rules.

## Decisions

1. **Platform destination is required configuration.** `destination_for` for `scope=platform` reads the operator configuration as required and requires a non-empty `[promotion].repo`; otherwise it raises `RuntimeError` naming `[promotion].repo` and the operator configuration. Inside `route_event` this becomes a `pending` route whose detail names the setting, so the event stays local and visible in route state, doctor/finish warnings, and `route-pending` output (`failures`). It is never routed to `origin`. `scope=project` keeps routing to origin, which is its defined destination. `platform_repository()` uses the same required read and raises.
   *Alternative rejected:* hard-failing the whole `route-pending` run on the first configuration error — it would hide the remaining project-scope events, and doctor/finish already surface failures as warnings; quieting or blocking those commands belongs to a sibling Requirement.
2. **Label configuration errors propagate.** `process_label()` no longer catches `FileNotFoundError/OSError/ValueError`; an empty or non-string configured value raises. An absent optional key keeps the documented default `process` (an optional setting, not an error).
3. **Strict local log with an explicit gap context.** `read_events` raises `FrictionLogError` (a `SystemExit`-compatible named error) with `path:line` for invalid JSON, a non-object line or a missing/invalid `at`, and with the path for an unreadable file. A context manager `tolerate_local_gap()` makes the reader skip invalid lines (and return no events for an unreadable file); it is entered only by review-path (which already reports the degraded source) and by checkpoint when `friction-log` is in `--accept-gap`. `_local_source_status` uses the same strict parser over the whole log, so status and reader agree.
4. **Position-independent legacy identity.** An id-less line gets `legacy-` + first 16 hex chars of SHA-256 of the stripped line. Persisted `legacy-<digits>` keys in route state and attribution records are translated on read to the content id of line N when that line exists and has no own id; otherwise a named error. The attribution file stays append-only and is not rewritten.

## Risks / Trade-offs

- A downstream project that relied on the origin fallback for platform events now keeps them pending until `[promotion].repo` is configured; the pending reason names the setting. This is the intended behaviour.
- A previously tolerated malformed log line now stops commands that read events; the error names file and line so the operator can repair it, and the explicit gap acceptance remains available for checkpoints.
