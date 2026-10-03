# Verification: reliable short retrospective

OpenSpec-Verify: PASS
Verification-Method: Manual scenario-by-scenario review of Requirement development-backlog#301, the proposal, design, three delta specifications, the implementation in agent_friction.py and requirement_retrospective.py, the workflow docs and the new regression tests; strict OpenSpec validation and the platform check suite.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Attribution: new events default to the current task branch (explicit `--task` wins; integration branch or unknown branch is marked unattributed). Legacy `task=null` events are recovered through `branch`/`run.source_issue` without being rewritten, and events with no attribution evidence are reported as ambiguous in `review-path` and checkpoint output, never assigned to the task under review. Mandatory signals (lifecycle failures and workaround/override/recurrence/drift events) must be linked or classified resolved-in-task, already-recorded or expected-behavior; known-recurrence occurrences can only be linked. A partial or unreadable friction log blocks `none` until named with `--accept-gap`. The Requirement checkpoint uses the same helpers. `review-path` prints the shared five-point template and up to five project questions from `dev-platform/retrospective.toml`, path-scoped, shipped skip-if-exists through Copier; absence or an invalid file leaves the shared path working.

Not exercised: a real Copier update of a downstream project (the file is project-owned and listed in `_skip_if_exists`; the script change reaches projects through the normal template update). Pre-authoring state is intentionally not an evidence source, so it cannot be reported unavailable.

Checks completed before archive:

- `python3 -m pytest tests/test_retrospective_attribution.py tests/test_friction_review.py tests/test_requirement_retrospective.py` — 76 passed (20 new, including #284-shaped omitted-signal, lost-attribution, clean-path, explained-expected-failure, recurrence and degraded-source cases for task and Requirement).
- `python3 scripts/run_test_groups.py --all` — all 15 groups passed.
- `python3 scripts/managed_projects.py validate` — passed.
- `openspec validate reliable-short-retrospective --strict` — passed.

Independent review (spec-fidelity and engineering-quality) returned six advisory findings. Fixed: stale disposition sentence in both workflow docs, design text claiming a pre-authoring evidence source, sticky whole-file malformed-line gap (now the latest 500 lines), untested managed-task alias recovery (test added). Accepted as is: informational `ambiguous_attribution` listing on checkpoint output, bounded to a 14-day window and ten ids, because unattributed events must not disappear silently.
