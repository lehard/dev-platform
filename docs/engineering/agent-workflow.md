# Agent workflow (central repository)

This is the detailed operating guidance for working *in* `dev-platform` itself. `AGENTS.md` is the bounded always-on map and remains the canonical entrypoint; this document holds the workflow detail that is only needed once a task reaches the relevant concern.

For the guidance rendered into downstream managed projects, see `template/docs/engineering/agent-workflow.md`.

## Task intents

Four intents stay distinct.

**Discuss.** Inspect, design and compare options. A substantial discussion does not by itself create Backlog state.

**Fix/add to Backlog.** When the user explicitly asks to record an accepted non-trivial change ("зафиксируй", "добавь в бэклог", "создай задачу" or equivalent), prepare a local authoring bundle and run:

```bash
python3 scripts/managed_task.py create --bundle <directory>
```

The bundle contains `manifest.json` (`title`, `change`, ordered `artifacts`), `issue.md`, and those artifacts. The helper validates the configured Backlog contract and the temporary OpenSpec change against a short-lived checkout of the exact `prepared_against` revision it records (never a possibly-stale local working tree), performs bounded duplicate checking, publishes one `managed-openspec:v1` package carrying bounded source-Issue revision evidence (`updated_at` plus a normalized title/body hash). The deterministic managed-task authoring receipt is excluded from that hash; human title/body scope edits remain drift evidence. The helper then stops. Review potential-overlap candidates and pass `--confirm-distinct` only after deciding the scopes are separate. Do not implement, apply, dispatch, publish, or change Project state after authoring; wait for a separate execution request.

If the source Issue is edited after authoring but before `start_managed_task.py`/`managed_task.py` materializes it, start stops with an actionable diagnostic naming the recorded and current body hashes; either author a superseding package or rerun with `--acknowledge-source-issue-revision <current_body_sha256>` to explicitly keep the existing package's scope. Once a package is materialized, local OpenSpec stays canonical -- later Issue edits never rewrite it automatically; `dogfood_task.py status --json`/`finish_task.py --status --json` instead expose a bounded `source_issue_drift` field for the human/agent to notice.

A published package that fails supported intake validation, or whose pre-execution scope needs revising, is replaced with:

```bash
python3 scripts/managed_task.py supersede --bundle <directory> owner/repo#N
```

`supersede` validates the replacement against the exact current target state before activating it, rewrites the predecessor comment with a bounded `supersedes` link rather than leaving two ambiguous active packages, and is refused once the task has already reached `In review`/`Done` Project status. Retrying with an unchanged bundle converges as a no-op.

When accepted process evidence explicitly motivates the work, pass a repeatable
`--process-evidence owner/repo#N` for each source issue. The package, not a
full-text comment search, is canonical. Eligible evidence is marked
`process:managed` with one bounded backlink after the task exists, then remains
open until terminal managed success.

Authoring also records a provider-neutral recommended start tier (`R2` balanced by default) and prefixes the created Issue title with `[R2]`. Pass `--strong-trigger <category>` only when a concrete hard trigger applies (see [docs/engineering/model-routing.md](model-routing.md)) to recommend `R3` instead; diff size, file count or blast radius alone are never a valid reason to pass it.

**Quick execution.** A small direct request may use the existing task/check/finish workflow without creating a backlog issue or ceremonial OpenSpec. If it expands into a material behavior, architecture, compatibility, data-contract, or scope change (or needs a full active OpenSpec contract), stop implementation and enter managed intake before continuing instead of broadening it silently.

**Fresh non-trivial execution.** An explicit request to implement material work creates or reuses the managed task and starts that same task before implementation. Prepare the normal authoring bundle, then run `python3 scripts/execute_managed_task.py --bundle <directory>`. The composed helper is idempotent across authoring and start interruptions. The detailed shared intent contract lives in [task-intake.md](task-intake.md).

**Execute an existing managed task.** An explicitly supplied Development Backlog issue is a managed task. Run:

```bash
python3 scripts/start_managed_task.py owner/repo#N
```

It performs read-only package intake, creates the task branch/worktree, materializes the agreed package only in that task checkout, then reconciles the configured Development Backlog Project item to `In progress`. It does not start apply, dispatch, or publication. Missing Project configuration/permission is a resumable start blocker, not a silent stale `Ready` state. `managed_task.py` is a task-checkout-only importer for recovery and light-profile use; it must not materialize files in a feature-capable integration checkout.

Then compare the materialized change with current specs and active changes. Repair formal/schema mismatches, but stop for user resolution if the product contract materially conflicts.

After successful import, the local `openspec/changes/<change>/` artifacts are canonical for implementation, verification, and archive. The backlog issue remains the human-facing provenance item, not a competing implementation task list.

## Development Backlog Project state

For managed tasks, publication reconciles an exact reviewable PR to `In review`, and terminal finish reconciles `Done` only after GitHub merge/direct delivery plus required local synchronization. Ordinary CI waiting remains `In review`.

Use `python3 scripts/managed_project_status.py block --reason "..."` only for a genuine external/human stop, `resume` after it clears, and `status --json` for read-only recovery evidence. These commands require GitHub Projects read/write authorization (`gh auth refresh -s project`). Quick tasks without managed provenance do not mutate the Development Backlog Project.

## Selective goal definition

Refine a goal before OpenSpec or managed-task authoring only when the user explicitly requests goal-backed work, or when a non-trivial request is materially unclear about its intended outcome or success evidence. Do not require goal creation for an ordinary concrete quick or implementation task.

A usable goal states the concrete outcome, verification evidence, a meaningful quantitative or binary success threshold, relevant scope bounds, and the condition that should stop work for clarification. If a missing choice could change the intended result, ask one concise question instead of inventing the requirement.

For an explicit goal-backed request, use supported native goal state through `/goal` or runtime-native goal tools when available, and inspect any active goal before creating a duplicate or conflicting one. Include a token budget only when the user explicitly requests one. A fuzzy request that the user did not ask to make goal-backed receives transient natural-language refinement, not implicit durable goal state. If native goal state was explicitly requested but is unavailable, perform an explicitly transient refinement or report the limitation; never claim that `create_goal` succeeded or that an active goal exists when the runtime cannot prove it.

Goal refinement creates no goal file, backlog entry, decision log, resume artifact, or competing implementation plan. For managed work, the refined outcome informs the Issue/OpenSpec package; after materialization, that package remains canonical.

## Central source dogfood lifecycle

For ordinary work in this central repository, use the committed source contract in `.dev-platform.toml` and its lifecycle adapter. Do not assemble a manual branch/worktree/PR flow. A managed task is imported first, then its sole untracked package is transferred into the isolated task worktree:

```bash
python3 scripts/start_managed_task.py owner/repo#N
cd .claude/worktrees/<change>
python3 scripts/dogfood_task.py status
python3 scripts/dogfood_task.py reconcile
python3 scripts/dogfood_task.py finish
```

`managed_task.py owner/repo#N` alone refuses to run directly on this repository's own integration checkout (`harness_mode=platform`, `workflow_profile=multi-agent`) and points here instead; `start_managed_task.py` performs the same read-only package intake from outside that checkout, then creates/reuses the task worktree/branch itself. For a change lacking `.managed-task.json` provenance from before that enforcement existed, see the recovery evidence in `lehard/dev-platform#204`.

`status` is read-only and reports task-vs-authoritative-main freshness before costly validation; for a managed task it also carries a bounded, best-effort `source_issue_drift` field (whether the source Issue's title/body changed since authoring) as evidence only -- local OpenSpec stays canonical and is never rewritten from it. Run `python3 scripts/dogfood_task.py status --json` for the exact machine-readable recovery surface. If `status` reports `behind` or `diverged`, run `reconcile`: the explicit operation refuses dirty/provenance-ambiguous/changed-remote state and uses a normal merge only, never a rebase, force-push, reset or automatic stash. A reconciled head must rerun validation before `finish`, which delegates to the authoritative GitHub-backed publication/reconciliation lifecycle and is resumable; branch pushed, draft or open PR, and green checks are nonterminal states. Do not report source work as complete until GitHub reports the exact PR `MERGED` and local `main` has been reconciled (with cleanup warnings classified under the shared lifecycle policy).

If terminal reconciliation succeeds while the invoking shell still has the task worktree as its cwd, finish records exact worktree/branch/head cleanup metadata instead of deleting that cwd synchronously. This is a successful delivery with deferred housekeeping; from the surviving integration checkout, run the exact targeted recovery command printed by finish. Recovery verifies the recorded identity and current process/board/cleanliness state before removal, and is idempotent. Global cleanup is deliberately two-step: `python3 scripts/worktree_cleanup.py cleanup --all` previews the bounded candidate set, and `python3 scripts/worktree_cleanup.py cleanup --all --apply` performs the reviewed global action.

## Scope discipline and capabilities

Promote a rule/tool only when it is reusable across projects or a defined workflow profile. Keep application-domain rules, credentials, machine-local paths and one-off workarounds in the owning project.

A change to a downstream managed file must consider both new-project rendering and Copier update behavior for existing projects.

The shared lifecycle is composable. `light`, `standard`, and `multi-agent` profiles select capabilities rather than forking the template. GitHub sync/publish, checks, OpenSpec policy and release pinning are core; worktrees/board are multi-agent capabilities.

## Validation

At minimum:

```bash
python3 -m compileall -q template/scripts scripts
python3 scripts/managed_projects.py validate
python3 scripts/run_test_groups.py --all
python3 template/scripts/openspec_lifecycle.py check
```

When Copier is available, render the template and compile/run the generated doctor. For Git lifecycle changes, exercise temporary local/bare remotes so fetch/sync/direct-publish safety is tested.

For a bounded local change, prefer `python3 scripts/select_checks.py --base origin/main --execute` over the full command list above: a semantic-preserving `AGENTS.md`/`docs/**`/OpenSpec-prose/`template/AGENTS.md.jinja` change gets bounded structure/link/anchor/render checks instead of the full suite, a proven executable-surface change gets its mapped test group(s), and an unknown, ambiguous or control-plane (selector/CI/lifecycle) path still fails closed to the full set above. This never replaces the protected-full result required for a PR.

## Friction routing

Raw friction evidence stays machine-local. Record high-signal events through `scripts/agent_friction.py`; the normal path automatically upserts a bounded sanitized, fingerprinted process issue in the configured project or platform repository. Retry failure is durable and non-blocking for safe delivery. Process issues are evidence only: cloud triage/review must never create managed tasks, OpenSpec, implementation PRs, or code changes.

The periodic Process Health Review is advisory and read-only. Its dated report
records `reviewed_at`, the exact `main` SHA, and its previous-review boundary;
it reads bounded current managed-work and merged-change context, clusters
symptoms by likely root cause, and verifies likely-resolved candidates against
current repository evidence. It does not add ritual source-issue comments,
create work, or resolve source issues. Explicitly linked evidence is closed
only after the existing terminal merge, local reconciliation, and Project-Done
path succeeds.

The weekly cloud Process Health Review is the routine cadence. Local friction
`pending`/`review` commands remain recovery and diagnostic surfaces rather than
actions required from each current task agent. `reconcile-process-labels` is a
bounded, idempotent recovery operation: it restores the configured `process`
label only on unmistakably router-generated open source issues.

Record only high-signal friction: user correction, repeated failure, safety near-miss, undocumented invariant or excessive retries. Separate observation, evidence, hypothesis and proposal. Do not record secrets or routine successful sessions. When a finding concerns a specific participant, pass `--participant-role supervisor|executor`; the identity is read back from the current routing record rather than self-reported (see `docs/engineering/model-routing.md#execution-provenance`). Friction fingerprinting never includes model/provider, so the same recurring problem across different models still updates one issue.

### Post-task retrospective

Before non-trivial completion, run a distinct post-task retrospective -- not merely picking a checkpoint value. Review the task for user corrections, repeated substantive failures/retries, manual workarounds, safety near-misses, false premises, undocumented invariants, missing automation/documentation, tooling/auth/worktree/Git/OpenSpec/CI/lifecycle friction, avoidable repeated work, and problems noticed but left unresolved. Classify each candidate as already resolved in this task, already represented by an existing recorded event, or new and meaningful; record only the last class.

The retrospective also reads the current task's existing high-signal `lifecycle-*` failure records from the friction log. It does not add a task-outcome database: a lifecycle failure must be classified as `resolved-in-task`, `already-recorded`, or `new-recorded` before the checkpoint can succeed. Clean tasks have no such records and retain the one-command `none` path.

```bash
python3 scripts/agent_friction.py checkpoint --result none
python3 scripts/agent_friction.py checkpoint --event <id> [--event <id> ...]
python3 scripts/agent_friction.py checkpoint --result none --lifecycle-disposition <event-id>=resolved-in-task|already-recorded
```

`--result none` is valid only after the retrospective actually ran and found nothing new and every current-task high-signal lifecycle failure has an explicit disposition. Referencing its recorded event is the `new-recorded` disposition; `--lifecycle-disposition` is for the resolved/already-recorded cases. The checkpoint binds to the current branch and Git head; `require_checkpoint` rejects it as stale once new commits land (a fresh retrospective is then required), rejects a checkpoint referencing an unknown event id, and rechecks for newly unclassified lifecycle failures. A missing/stale/unclassified checkpoint blocks `finish_task.py` with an actionable instruction -- it never invents `none`.

## Completion

Before reporting a non-trivial platform task as complete:

- active OpenSpec artifacts still describe what was actually built;
- required checks pass or deviations are explicit;
- semantic OpenSpec verification has been run and material findings resolved;
- `verification.md` contains `OpenSpec-Verify: PASS` and a truthful `Verification-Method`;
- the OpenSpec change has been archived through the lifecycle helper and the resulting spec/archive changes are committed;
- the task is published according to the configured mode;
- temporary machine-local artifacts are not tracked;
- the post-task retrospective ran and the friction checkpoint reflects its current result.

The final report states that the retrospective ran and either lists its findings or says explicitly that none were found. If any required completion step is blocked, report the blocker instead of saying the task is done.
