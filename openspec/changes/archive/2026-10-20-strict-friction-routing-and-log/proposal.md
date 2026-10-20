## Why

The friction router silently substitutes values when configuration or evidence is missing. `destination_for` and `platform_repository` route a `scope=platform` event to the project's own origin when `promotion.repo` is absent or the operator configuration cannot be read; this put 51 platform issues into a project repository. `process_label()` swallows configuration read errors and returns the default label. `read_events` drops malformed log lines, returns an empty list for an unreadable log, and gives id-less legacy events a `legacy-N` id derived from the line position, which `attribute --id` then persists. The owner rule for this platform is explicit failure instead of fallbacks.

## What Changes

- Routing a `scope=platform` event requires a configured platform repository (`[promotion].repo` in the enabled operator configuration). When it is absent, or the operator configuration cannot be read, routing stops with an error that names the missing setting; the event stays local with that reason and is never sent to the project origin. `platform_repository()` (label reconciliation) applies the same rule.
- `process_label()` propagates configuration read errors and rejects an empty or non-string configured value instead of returning the default label. The documented default for an absent optional `process_health.process_label` key is unchanged.
- `read_events` reads the local log strictly: an unreadable log or a malformed/non-object/undated line raises an error naming the file and line. The only tolerant read is an explicit gap context used where the gap is reported (review-path) or explicitly accepted (`--accept-gap friction-log`), mirroring the existing coordinator-evidence gap handling.
- An event recorded without an id receives a content-derived identity (`legacy-<digest>` of its exact line), independent of its position. Previously persisted positional `legacy-N` references in route state and attributions are translated deterministically to the content identity of line N; a positional reference that does not resolve to an id-less line is a named error.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: friction routing destination and local friction log reading.

## Impact

- `template/scripts/agent_friction.py` (rendered into managed projects) and its tests.
- Projects routing platform events without `[promotion].repo` now see a named pending-routing reason instead of issues created in their own repository.
