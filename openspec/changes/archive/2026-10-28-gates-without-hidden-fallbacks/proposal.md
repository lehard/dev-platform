## Why

Three gates still hide a missing input. The finish private-reference guard and `project_publish` skip silently when `scripts/check_private_backlog_refs.py` is absent, even in a checkout that enables private lineage, so a lost guard publishes unchecked. `select_checks.py` without `--base` diffs `HEAD~1..HEAD`, and it ignores a failing `git diff`, so a run can select checks for the wrong change set and still produce green evidence. The owner decided (2026-10-27, variant A) that the guard is mandatory where `private_lineage.enabled` and reports "not applicable by configuration" elsewhere. The `agent_friction` checkpoint reported false staleness: an unreadable task state or content proof was swallowed and shown as a stale retrospective.

## What Changes

- `template/scripts/private_lineage.py`: one helper decides the guard: enabled and guard present -> run it; enabled and guard missing -> blocker naming the script; disabled -> the caller prints "private-reference guard: not applicable by configuration (private_lineage not enabled)".
- `template/scripts/finish_task.py` `observe_private_reference_blocker` (preflight, developer handoff, publication recheck) and `template/scripts/project_publish.py` (`_safe_presentation` and the publish path) use that helper instead of `if guard.is_file()`.
- `template/scripts/select_checks.py`: `changed_files` resolves the base explicitly: `--changed-file` as given; `--base` as given; otherwise a task branch uses `origin/<main_branch>` and prints it; the main branch or a detached HEAD without `--base` fails naming the options. A failing `git diff` fails naming the command and git's message. The `HEAD~1..HEAD` fallback is removed.
- `scripts/select_checks.py` resolves the base by the same function before running the selector, so the Explorer drift step never runs without a base.
- `template/scripts/agent_friction.py` `current_task_content`: the false staleness reproduces as a swallowed error. Any exception while reading the managed task state or its content proof returned `None`, which `require_checkpoint` then reported as "retrospective is stale". The catch is removed; a quick task (no managed state) still has no proof.
- Tests: guard enabled/missing/disabled in finish and publish; select-checks base cases (explicit, task branch, main, detached, git failure); `agent_friction` content proof propagates a task-state error and returns no proof for a quick task (freshness across a lifecycle-only head change and staleness on a content change are already covered).
- `docs/engineering/agent-workflow.md`: the base rule for `select_checks.py`; `docs/engineering/openspec-workflow.md`: the guard rule for finish and publication.

## Impact

- About 15 files under `template/scripts/`, `scripts/`, `tests/` and `docs/`.
- Specs: completion-lifecycle (one MODIFIED requirement), gate-fail-explicit (one ADDED requirement).
- Downstream: rendered projects without private lineage now see one "not applicable by configuration" line; a project calling `select_checks.py` on its main branch without `--base` must pass `--base` or `--changed-file`.
