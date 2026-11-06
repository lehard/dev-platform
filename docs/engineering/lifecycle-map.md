# Task lifecycle map

This document maps how one unit of work moves from a Business Requirement to merge, release and rollout. For each stage it names the actor, the entry and where the stage's state lives. The rationale is [DEC-0009](../decisions/0009-single-stream-core.md), which replaced the queue-based target of [DEC-0008](../decisions/0008-target-task-lifecycle.md).

The platform and every project take the same path. No project has a publication queue or hosted lifecycle workers, and neither does this repository: the profiles `light`, `standard` and `multi-agent` differ in worktrees and the board, not in who merges.

## Actors

| Actor | What it is | Decides or does |
| --- | --- | --- |
| Owner | the human | product meaning, ADD approval, risk acceptance, release and rollout |
| Coordinator | the chat coordinator session | the roadmap, starting the one stream, owner escalations; writes no task code |
| Developer | the one writing agent, in the task worktree | pre-authoring, OpenSpec authoring, implementation, checks, `finish` |
| GitHub | required checks and auto-merge | merge into `main` |

## Lifecycle

| # | Stage | Entry | Actor | Produces |
| --- | --- | --- | --- | --- |
| 1 | Fixation | `requirement_intake.py create` | developer at the owner's request | `type:requirement` Issue, Backlog card |
| 2 | Pre-authoring | `requirement_intake.py start`, then `orchestrate_pre_authoring.py` and `add_intents.py` | developer; owner approves the ADD | snapshot, ADD, intents, handoffs under `.claude/pre-authoring/` |
| 3 | Child creation | `requirement_intake.py materialize-handoff` / `link-child` | developer | `type:internal-change` Issue with an R2/R3 start tier |
| 4 | Start | `execute_requirement.py advance`, `start_managed_task.py`, `execute_managed_task.py`, `dogfood_task.py start` (with `--change` for a managed task), `start_task.py` in a project, `start_worktree.py` (plus `agent_board.py start`) | developer | worktree, board claim, `.managed-task-state.json` |
| 5 | Routing | `dogfood_task.py route-claude --tier R1/R2/R3` | developer | routing receipt |
| 6 | Implementation and checks | `select_checks.py --execute --evidence`, then `verification.md` | developer | content-bound evidence |
| 7 | Finish | `dogfood_task.py finish`: optional review, `finalize_change` (archive, all prerequisites at once), friction checkpoint, PR, `gh pr merge --auto --squash --match-head-commit`, then following the PR to `MERGED` | developer | archived change, exact-head PR merged and local main synchronized |
| 8 | Merge | GitHub on green required checks | GitHub | merged PR |
| 9 | Reconcile | rerun of `finish` after the merge: local main, Project card, parent Requirement, cleanup | developer | task Done, Requirement closed when every child is Done |
| 10 | Shared delivery (two or more children) | `execute_requirement.py advance` through `requirement_integration.py` | developer | one shared PR, then stages 8 and 9 |
| 11 | Release | release PR changing `VERSION` → `publish-version.yml` | owner | immutable tag |
| 12 | Rollout | manual **Roll Out Platform** dispatch | owner | downstream PRs |

A quick task runs `dogfood_task.py start --task` → `finish` here (`start_task.py` in a project) and skips stages 1–3 and 5.

Publication refuses when no required check gates the merge, and it never falls back to another merge form. Independent review is optional and runs in stage 7 only with `[independent_review] enabled = true`; `scripts/independent_review.py` runs it by hand.

## Where state lives

- **Task**: the board claim, the worktree and the OpenSpec change; local JSON is a cache.
- **Publication**: the exact-head PR and GitHub's auto-merge state.
- **Requirement**: the Issue, with status derived from its children (`requirement_intake.py aggregate`).

## What is still tangled

- **Start** has several entries plus board registration, each leaving different local state.
- **Recovery** is spread over `requirement_integration.py recover`, `requirement_merge_recovery.py`, `dogfood_task.py reconcile` and `finish_task.py --reconcile`.
- **Accepted specs** overlap: `platform-`, `completion-`, `central-dogfood-` and `standard-profile-lifecycle`, and three shared-workspace specs.
