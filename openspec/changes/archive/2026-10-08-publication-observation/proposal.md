## Why

The coordinator decides lifecycle transitions from four GitHub-derived observations, and each currently degrades silently or terminally:

- `publication_queue._comments` reads one page (`per_page=100`), raises when the page holds 100 rows, and silently drops non-object rows. Long-lived PRs stall and malformed history is consumed as if complete.
- `publication_state.required_check_state_for_ref` returns a cause-less "unknown" for any unusable observation and does not re-read the PR head after reading checks, and `publication_queue._integrate` turns every "unknown" into a `QueueError` that `_block`s the candidate terminally instead of waiting or repairing. With `--required`, a pull request whose base has no required checks (every Requirement contribution PR to an unprotected `requirement/BR-<n>` integration branch) exits 1 without JSON, so contributions can never record a passed required-checks gate (verified with gh 2.97 during implementation).
- `publication_queue.trusted_apps` wraps each configuration reader in `except Exception: continue`, so an unreadable or invalid config silently narrows the trusted coordinator-App set.
- `publication_queue._admission_handoff` swallows every error while proving task content (and `agent_friction.current_task_content` is documented best-effort), so a managed candidate whose proof cannot be read is admitted with quick-task branch/head identity.

The existing publication-queue spec already requires complete trusted comment history and exact-head, content-bound handoff; the code contradicts it.

## What Changes

- Read the whole PR comment history through one paginated, validated, ordered observation; a named error on transport, shape or ordering failure; no partial or filtered history.
- Classify required checks from valid gh JSON for exit statuses 0, 1 and 8, keep passed/pending/failed/not_registered distinct from unusable observations carrying an explicit cause (transport, malformed, head-mismatch), and re-bind the snapshot to the expected PR head.
- Make the coordinator treat a pending check as waiting, a failed check as a bounded repair, a head mismatch or transport failure as an explicit non-terminal wait with a named reason, and reserve terminal blocks for genuine contract violations.
- Make trusted-App configuration readers fail closed with a named error; absence of an optional source stays valid, unreadable or invalid configured sources do not.
- Require managed task-content provenance at queue admission: detect managed candidates from authoritative state, read the proof strictly, and fail rather than substituting quick-task identity.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `publication-queue`: complete validated comment history, exact-head required-check observation semantics, fail-closed trust configuration, managed provenance at admission.

## Impact

Platform-owned `template/scripts/publication_queue.py`, `template/scripts/publication_state.py` (and its consumers `project_publish.py`, `finish_task.py`, `rollout_preflight.py` only through the extended `RequiredCheckState`), and regression tests in `tests/test_publication_queue.py` and `tests/test_publication_state.py`. `scripts/` shims and the rendered template follow the same implementation. Marker authentication, exact-head state rules and the existing quick-task contract remain authoritative.

## Success Criteria

- Histories of 0, 99, 100, 101 and 200 comments are returned complete and ordered; later-page trusted markers participate in replay; malformed or failing pagination never yields a prefix.
- Real gh check output classifies as passed, pending, failed or not_registered (the latter decided from branch protection), contribution PRs are checked against the main branch's required checks, unusable observations carry a cause, pending never blocks a candidate terminally and a repairable failure enters the bounded repair path.
- An invalid configured trust source stops the operation with an error naming that source.
- A managed candidate without valid exact task-content provenance is not admitted and never receives branch/head identity.

## Non-goals

Worker identity, repair-provider routing, project runtime, durable evidence, preflight, downstream archive boundary, stable tagging and rollout, remote reviewer, TeamAI, economy routing, legacy cleanup, and independently tracked pre-release Requirements (#386, #376, #380/#382, #367, #403, #391). Best-effort `agent_friction.current_task_content` keeps serving its friction-binding callers; it is only no longer used by queue admission.
