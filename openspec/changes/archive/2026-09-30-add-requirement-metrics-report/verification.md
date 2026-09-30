# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the proposal, design (including the implementation clarifications in section 9), the requirement-metrics and completion-lifecycle deltas and the implementation against the Requirement acceptance evidence; strict OpenSpec validation (1.13.2); targeted unit tests; a representative dogfood of the new command against already completed Requirements; the archive helper's automated platform checks; and the platform-launched independent review of the committed candidate that archive runs.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Semantic review

- `requirement_metrics.py report` and `aggregate` are read-only. They print to stdout only, never write files, caches, comments, labels, Project fields or git refs, and read GitHub only through GET requests with bounded pagination. With `--offline`, the remote-dependent sections are `unknown`/`partial` with reason `offline`.
- Every metric leaf is `{value, status, sources}` and carries a `reason` when not measured. Totals over unknown inputs become `partial` or `unknown`, never zero. Counts rebuilt from published PR history are labelled `published-history-lower-bound`. A routing record whose `source_issue` does not match the child is reported as unknown instead of being used.
- Independent review cost: rounds are rebuilt from the review evidence at each published PR commit plus the archived final evidence. The report shows per-perspective reviewer provider/model with source, launches, wall time, findings by severity and dispositions. Reruns are classified as substantive candidate change, reviewer unavailable, or process rerun. Full-validation and CI cycles after the first review round are counted.
- Reviewer runtime usage: new available review reports carry a runtime-local `runtime_usage` block. Claude uses its four usage counters plus turns/duration fields, and Codex uses a single `turn.completed` usage. Cost fields are never kept. Anything absent, malformed or ambiguous is unknown. Report validation ignores the block, and historical reports read as unknown.
- Session signals: the Claude Code transcript adapter reports only counters, durations, session ids and the attribution method (exact child branch or exact reference span, with overlap marked `shared-session`). Other runtimes report `unsupported-runtime`.
- Aggregate: rows sit side by side, groups are keyed by child count, task family and start tier (medians only when n ≥ 5, otherwise `insufficient`), and runtime-keyed usage/session groups are never summed across runtimes. There is no score, only a fixed advisory note.

## Observed checks

- `python3 -m unittest tests.test_requirement_metrics tests.test_independent_review` passed (69 tests). This includes the privacy test, which asserts that no fixture text reaches the output, and the runtime-usage parsing and validation tests.
- `python3 scripts/run_test_groups.py --verify-coverage` passed. The docs parity/contract tests and `DEV_PLATFORM_TEST_JOBS=3 python3 scripts/run_test_groups.py --group fast-b` passed.
- `python3 -m compileall`, `ruff`, `check_docs_links.py`, `git diff --check` and the private-reference guard were clean.
- `openspec validate add-requirement-metrics-report --strict` passed.

## Dogfood

The command was run without any manual input against two already completed Requirements. Each child had a single change delivered through one PR.

- Requirement 176, which introduced the mandatory review gate: cycle time 618537 s, 13 observed stages (depth selection has no timestamp in its source). The review section shows 4 rounds (a lower bound), 8 launches, 274 s reviewer wall time and 2 material findings. It classifies 3 reruns as substantive candidate changes. After the first review it counts 3 full validations (about 1115 s) and 2 CI cycles, with 9 CI runs of which 2 failed. It also shows 2 publication cycles, 1 queue block and 14 friction events. Reviewer token usage is unknown because those reports predate the usage block.
- Requirement 275, which stabilized review cycles: cycle time 4260 s, 1 review round, 2 launches, 31 s wall time, 0 reruns, 1 full validation, 1 CI cycle.
- `aggregate` over both shows the two rows side by side with every comparison group at `insufficient` adequacy. The JSON output contains only identifiers, timestamps, counts, durations, statuses, source references and the fixed advisory note.
- Each value traces to a named source reference: an archived evidence file with blob identity, `gh:commit:<sha>:<path>` for published review/validation evidence, `gh:run:<id>`, `gh:pr`, `gh:issue`, or a local routing/pre-authoring/friction file.

## Post-archive review follow-up

The first platform-launched review reported no material findings and six advisory ones. Five of them were addressed after archive because they conflicted with the capability's own contract or hardened its privacy boundary:

- Offline totals for an unknown child set stay unknown instead of becoming a partial zero.
- Dispositions are attached per review round from every published disposition version.
- `--closed-since` paginates and marks a truncated selection partial.
- One child's malformed or unreadable source degrades only that child.
- Reviewer usage is read through an allowlist of runtimes and fields.

The remote call volume per child remains a documented trade-off. After the fix, the targeted unit tests (77), test-group coverage, strict validation of all specs and the private-reference guard passed, and the dogfood reports for Requirement 176 (online and offline) were re-run. The fixed candidate is reviewed again by the platform, and its automated-check evidence is refreshed.
