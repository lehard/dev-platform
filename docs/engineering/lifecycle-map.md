# Task lifecycle map

This document maps how one unit of work moves from a Business Requirement to merge, release and rollout. For each stage it names the actor, the entry and where the stage's state lives. It also records the approved **target** lifecycle that the simplification Requirements deliver, so it holds the current map and the destination side by side. The rationale is [DEC-0008](../decisions/0008-target-task-lifecycle.md). The detailed rules of each stage stay in their canonical documents ([task intake](task-intake.md), [agent workflow](agent-workflow.md), [OpenSpec workflow](openspec-workflow.md), [hosted lifecycle workers](hosted-lifecycle-workers.md), [chat coordinator](chat-coordinator.md), [release policy](../release-policy.md)); [OpenSpec](../../openspec/specs/) defines accepted executable behavior. Where this map and a spec differ, the spec governs until the corresponding simplification change lands.

## Actors

| Actor | What it is | Decides or does |
| --- | --- | --- |
| Owner | the human | product meaning, ADD approval, risk acceptance, release and rollout |
| Coordinator | the chat coordinator session | stream allocation, starting operator-node jobs, recovery, owner escalations; writes no task code |
| Developer | an agent in the task worktree | pre-authoring, OpenSpec authoring, implementation, checks, handoff |
| Hosted worker | `lifecycle-workers.yml` on GitHub Actions (every 10 minutes and after the queue) | review, finalize, integration-merge (`DEV_PLATFORM_HOSTED_KINDS`), except the composition jobs below |
| Operator node | `work-next --run` on the operator machine, started by the coordinator | repair, integration repair, a composition's finalize and full checks |
| Queue | `publication-queue.yml` with the GitHub App | merge into `main`, contribution integration |
| Post-merge runner | the LaunchAgent on the operator machine, every 10 minutes | retrospective, terminal reconciliation, cleanup |

### Job placement

| Job | Runs on | Started by |
| --- | --- | --- |
| `review` | hosted worker | automatically |
| `review` of a composition of a private Requirement | operator node | coordinator |
| `finalize` | hosted worker | automatically |
| `finalize` of a composition, with its full checks | operator node only | coordinator |
| `integration-merge` | hosted worker | automatically |
| `contribution-integration` | publication queue | automatically |
| `repair`, `integration-repair` | operator node | coordinator |
| `retrospective`, `terminal-reconciliation`, `cleanup` | post-merge runner on the operator machine | LaunchAgent, every 10 minutes |

The operator node is `lifecycle_workers.py work-next --run` on the operator machine. The coordinator also runs there a job that an automatic executor left unclaimed. Hosted kinds are the ones enabled in `DEV_PLATFORM_HOSTED_KINDS`.

## Current lifecycle

| # | Stage | Entry | Actor | Produces |
| --- | --- | --- | --- | --- |
| 1 | Fixation | `requirement_intake.py create` | developer at the owner's request | `type:requirement` Issue, Backlog card |
| 2 | Pre-authoring | `requirement_intake.py start`, then `orchestrate_pre_authoring.py` and `add_intents.py` | developer; owner approves the ADD | snapshot, ADD, intents, handoffs under `.claude/pre-authoring/` |
| 3 | Child creation | `requirement_intake.py materialize-handoff` / `link-child` | developer | `type:internal-change` Issue with an R2/R3 start tier |
| 4 | Start | six entries: `execute_requirement.py advance`, `start_managed_task.py`, `execute_managed_task.py`, `dogfood_task.py start --change`, `start_task.py`, `start_worktree.py` (plus `agent_board.py start`) | developer | worktree, board claim, `.managed-task-state.json` |
| 5 | Routing | `dogfood_task.py route-claude --tier R1/R2/R3` | developer | routing receipt |
| 6 | Implementation and checks | `select_checks.py --execute --evidence`, then `verification.md` | developer | content-bound evidence |
| 7 | Handoff | `dogfood_task.py finish` → `finish_developer_handoff` → `publication_queue.py admit`; friction checkpoint | developer | exact-head PR, v2 record, `lifecycle:review-pending`; claim released |
| 8 | Review | `lifecycle_workers.py work-next --kinds review` | hosted worker; operator node for a composition of a private Requirement | disposition or `repair-pending` |
| 9 | Repair | `work-next --kinds repair` | operator node, started by the coordinator | repair commit, re-review |
| 10 | Finalize | `work-next --kinds finalize` | hosted worker; operator node only for a composition | archive and re-run checks → `ready` |
| 11 | Merge | queue and `integration-merge` | queue, hosted worker | `lifecycle:merged` |
| 12 | Post-merge | `post_merge_runner.py` → retrospective → terminal reconciliation → cleanup | runner | `post-merge:settled`, Requirement Done, worktree removed |
| 13 | Composition (two or more children) | `requirement_integration.py` and `requirement_composition.py`, driven by `advance` | developer assembles; review and finalize as in stages 8 and 10 | shared `requirement/BR-N` PR through the queue |
| 14 | Release | release PR changing `VERSION` → `publish-version.yml` | owner | immutable tag |
| 15 | Rollout | manual **Roll Out Platform** dispatch | owner | downstream PRs |

A quick task runs `start_task.py` → `finish` → queue → post-merge and skips stages 1–3 and 5. A downstream `light` profile has no queue or workers: `finish` archives and publishes itself.

## Where the current lifecycle is tangled

- **Archive** is one function, `finalize_change`, which reports every unmet prerequisite at once and starts no review. It still has three callers: the finalize job, composition finalization (per child, in manifest order) and portable `finish`/`advance`. A developer does not archive: `openspec_lifecycle.py archive` without `--finalize` refuses.
- **Start** has six entries plus board registration, each leaving different local state.
- **Requirement retrospective and close** run only in the post-merge jobs under the queue, where `advance` stops at `await-post-merge`. Portable delivery still closes in session through the same functions, and `requirement_terminal.py reconcile` remains a coordinator recovery entry.
- **Recovery** is spread over five tools: `publication_queue.py` (`resume`, `switch-provider`, `reoffer-post-merge`, `restore-gates`), `requirement_integration.py recover`, `requirement_merge_recovery.py`, `dogfood_task.py reconcile` and `finish_task.py --reconcile`. A requirement branch adds `execute_requirement.py absorb-main` and `repair`.
- **Candidate state** is held in Issue and PR labels, the Project card, v1 admission comments and v2 records, the `publication:*` and `lifecycle:*` labels, local JSON, the board and journals.
- **Job placement** depends on the candidate as well as the job: a finalize runs hosted, but a composition's finalize and full checks need the operator node, because they read the managed project registry. So a composition waits for a coordinator-started run (see [Job placement](#job-placement)).
- **The task base** depends on what the task integrates into: `main`, or for a contribution its recorded `requirement/BR-N` target and contribution base. The evidence refresh hint still prints `--base origin/main` for a contribution, which widens its selection (see [agent workflow](agent-workflow.md#validation)).
- **Accepted specs** overlap: four lifecycle specs (`platform-`, `completion-`, `central-dogfood-` and `standard-profile-lifecycle`), three shared-workspace specs, and `publication-queue` beside `publication-recovery`.

## Target lifecycle

Principle: every stage has one actor, one entry and one place where its state lives. The developer's work ends at `finish`; automation does everything after that, and a human acts only on escalation.

```mermaid
flowchart LR
  subgraph Owner
    F[Fix BR] --> A{Approve ADD}
    REL[Release] --> RO[Rollout]
  end
  subgraph Developer
    PA[Pre-authoring] --> OS[OpenSpec and child]
    OS --> ST[start: one entry]
    ST --> IM[Implement, check, verify]
    IM --> HO[finish: handoff and friction checkpoint]
  end
  subgraph Workers[Hosted workers and queue]
    RV[Review] -->|findings| RP[Repair]
    RP --> RV
    RV -->|clean| FN[Finalize: the only archive]
    FN --> MG[Merge through the queue]
  end
  subgraph Runner[Post-merge runner]
    RT[Task and Requirement retrospective] --> TC[Requirement close] --> CL[Cleanup]
  end
  F --> PA
  A --> OS
  HO --> RV
  MG --> RT
  CL -.-> REL
  C[Coordinator: streams, escalations, repair, recover] -.-> RP
```

| # | Stage | Single entry | Single actor | Source of truth |
| --- | --- | --- | --- | --- |
| 1 | Fixation | `requirement_intake.py create` | developer on the owner's word | Issue |
| 2 | Pre-authoring and ADD approval | `requirement_intake.py start` → `orchestrate_pre_authoring.py` | developer; owner approves | `.claude/pre-authoring/` |
| 3 | OpenSpec and child | `materialize-handoff` | developer | change and child Issue |
| 4 | Start | `start <issue>`, which detects quick, managed or Requirement child | developer | board claim and worktree; local JSON is only a cache |
| 5 | Routing | `route-claude --tier R1/R2/R3` | developer | routing receipt |
| 6 | Implementation, checks, verification | `select_checks.py`, `verification.md` | developer | evidence bound to task content; a merge-only reconcile does not invalidate it |
| 7 | Handoff | `finish` | developer; developer work ends here | v2 queue record |
| 8 | Review and repair | jobs | hosted worker; the coordinator still starts repair | v2 record |
| 9 | Finalize | job | hosted worker; the only archive, checking every prerequisite at once | v2 record |
| 10 | Merge | queue | queue | `lifecycle:merged` |
| 11 | Retrospective, close, cleanup | jobs | post-merge runner only | `post-merge:settled`; card status derived from children |
| 12 | Composition | stages 7–11 for the shared PR, no separate archive | as above | v2 record of the shared PR |
| 13 | Recovery | `recover <PR or BR>` | coordinator | v2 record |
| 14 | Release and rollout | unchanged | owner | tag |

The downstream `light` profile has no queue. It uses the same finalize and post-merge functions, with `finish` calling them. The code is the same; only the actor differs.

## Delivery slices

The target lifecycle is delivered by small Requirements, at most two code streams at a time:

| Order | Slice | Depends on | Downstream impact |
| --- | --- | --- | --- |
| 0 | BR-939 then BR-924: post-merge runner throughput and attempt budget | — | PATCH/MINOR |
| 1 | BR-940 then BR-941: freshness of evidence, sequential Requirement children | a free stream | MINOR |
| 2 | BR-949: archive only in finalize, all prerequisites reported at once | OpenSpec split portion 3 (BR-799) | MINOR |
| 3 | BR-950 with BR-943: retrospective and Requirement close only in the post-merge runner | slice 0 | MINOR |
| 4 | BR-951: one `recover` | slice 2 | MINOR |
| 5 | BR-952: the v2 record as the only candidate state; v1 comments and `publication:*` removed | slice 4, empty queue | MINOR |
| 6 | BR-953 with BR-851: `--tier R1/R2/R3` | — | none |
| 7 | BR-954: merge overlapping spec families | all of BR-799 | none |
| 8 | BR-955 with BR-850: one `start` | slices 2–5 | MAJOR, after v4.0.0 |
| 9 | BR-946: documentation follows this map, including the coordinator role | slices 2–7 | none |

Delivered so far: slices 0 to 3 and BR-953 of slice 6. The rest is open.
