## Why

`retrospective`, `terminal-reconciliation` and `cleanup` are `UNHOSTED` in `hosted_workers.py` (they need machine-local state and Development Backlog access) and nothing schedules them on the Mac. On 2026-10-28, 32 merged PRs waited for a coordinator to run `lifecycle_workers.py work-next` by hand: one job per run, and the next job of the chain appears only after the previous result (30 PRs closed in 43 runs, about 62 minutes, no LLM needed) (BR-885).

## What Changes

- New platform script `scripts/post_merge_runner.py`: one scheduled *round* that repeatedly runs the existing `lifecycle_workers.py work-next --kinds retrospective,terminal-reconciliation,cleanup --run` as a subprocess until it reports `idle`, or the round hits its job, time, rate-limit or first-failure bound. It adds no queue, claim format or state of its own.
- Round guards: a non-blocking single-instance lock; a GitHub REST remainder check (`gh api rate_limit`, not counted) before the round and between jobs, skipping with a journal record below a required threshold; detection and journaling of an interrupted previous round.
- Append-only JSON Lines run journal (`post-merge-runs.jsonl`): round start/end, skips with reason, every `work-next` run with PR, kind, status, outcome, duration and remainder before/after, and failures with their message.
- `launchagent` subcommand that renders (and, on explicit request, installs or removes) `~/Library/LaunchAgents/dev.platform.post-merge-runner.plist` with fully explicit arguments, `RunAtLoad` and a 600 s `StartInterval`; `journal` subcommand to read recent records.
- Documentation of the owner install/rollback commands. Installing the agent is an owner step and is not part of this change's execution.

## Impact

- `scripts/post_merge_runner.py` (new), `tests/test_post_merge_runner.py` (new), `docs/engineering/chat-coordinator.md` is **not** touched (owned by BR-889/BR-886); the install guide goes to a new section in `docs/engineering/hosted-lifecycle-workers.md`.
- Spec: lifecycle-workers (added requirement). Platform manifest and test-group classification for the new files.
- Visibility on the PR and in `lifecycle_overview.py` of a spent post-merge obligation already exists (`post-merge-exhausted`, `ensure_post_merge_attention`) and is reused unchanged.
