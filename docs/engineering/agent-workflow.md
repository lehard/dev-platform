# Agent workflow (central repository)

This is the detailed operating guidance for working *in* `dev-platform` itself. `AGENTS.md` is the bounded always-on map and remains the canonical entrypoint; this document holds the workflow detail that is only needed once a task reaches the relevant concern.

For the guidance rendered into downstream managed projects, see `template/docs/engineering/agent-workflow.md.jinja`.

## Task intents

The canonical intent contract is [task-intake.md](task-intake.md). Keep the
following routes distinct.

**Discuss.** Inspect, design and compare options. A substantial discussion does
not by itself create Backlog state.

**Fix/add to Backlog.** When the user explicitly asks to record accepted
non-trivial work ("зафиксируй", "добавь в бэклог", "создай задачу", "отправь в
бэклог" or equivalent), author a human-facing Business Requirement and stop:

```bash
python3 scripts/requirement_intake.py create \
  --repository OWNER/DEVELOPMENT-BACKLOG \
  --title "<business requirement title>" \
  --outcome-file <outcome.md> \
  --target-repository OWNER/TARGET \
  [--context-file <context.md>] \
  [--acceptance-file <acceptance.md>] \
  [--exclusions-file <exclusions.md>]
```

The Requirement contains business intent only and is labeled
`type:requirement`. Fixation does not create `proposal.md`, `design.md`,
`tasks.md`, an OpenSpec delta, technical decomposition, execution state, or
implementation. A fixation-only request stops here.

**Quick execution.** A small direct request may use the existing
task/check/finish workflow without creating a Requirement, backlog issue, or
ceremonial OpenSpec. If it expands into a material behavior, architecture,
compatibility, data-contract, or scope change, stop implementation and enter
the appropriate non-trivial intake route before continuing.

**Fresh non-trivial execution / execute a Business Requirement.** By default,
material business/product work is requirement-first. Create/reuse the
Requirement if necessary, then run:

```bash
python3 scripts/requirement_intake.py start --requirement owner/repo#N
python3 scripts/orchestrate_pre_authoring.py status --id requirement-N
```

Drive the orchestrator resumably through a recorded depth selection. A
deterministic result goes directly to a handoff; bounded evidence requests only
scoped routine read-only projections; a material design delta continues through
snapshot -> ADD -> intents -> handoff. Surface a human question only when the
orchestrator reports a consequential unresolved choice.
For each ready handoff, author the resulting internal technical managed change
through the existing managed/OpenSpec path, then immediately link it:

```bash
python3 scripts/managed_task.py create --bundle <directory>
python3 scripts/requirement_intake.py link-child \
  --requirement owner/repo#N \
  --child owner/repo#M
python3 scripts/start_managed_task.py owner/repo#M
```

The child is labeled `type:internal-change`. Repeat once per handoff; one
Requirement may legitimately produce multiple technical children.
A direct deterministic or bounded-evidence handoff is one executable child.
One child finishes through its normal managed PR and exact merge; two or more
children use shared integration only when joint delivery is required. After
every mandatory child is delivered, terminal reconciliation marks the parent
Project card `Done` and closes its Issue. The operation is idempotent for older
delivered Requirements:
`python3 scripts/requirement_terminal.py reconcile --requirement owner/repo#N`.
No `Requirement-Integration-Exception` is required for an ordinary single child.

Requirement progress is a read-through projection from local pre-authoring evidence and
their real Project statuses:

```bash
python3 scripts/requirement_intake.py aggregate --requirement owner/repo#N
```

The compatible `status` field remains child-only; `progress` adds a
recomputable pre-authoring, design/decision, readiness, implementation,
blocked/unknown, or done stage with source diagnostics. Do not write a
parallel Requirement status ledger. The primary human-facing Project view
should show Requirements and filter out `type:internal-change`.

**Direct technical managed/OpenSpec path.** Preserve the existing path when the
user explicitly supplies a managed Development Backlog Issue/OpenSpec task or
explicitly asks to create a technical managed task. For technical authoring,
prepare the normal managed bundle and use:

```bash
python3 scripts/managed_task.py create --bundle <directory>
```

For an explicit technical create-and-run request use
`python3 scripts/execute_managed_task.py --bundle <directory>`; for an already
supplied managed Issue use
`python3 scripts/start_managed_task.py owner/repo#N`.

All existing managed-package safeguards remain unchanged on this direct/internal
technical path: exact-`prepared_against` validation, bounded duplicate
checking, one active `managed-openspec:v1` package, source-Issue revision
evidence, routing receipt, `supersede` for a pre-execution replacement, and
Project reconciliation on managed start. After materialization, the child's
local `openspec/changes/<change>/` artifacts are canonical for implementation,
verification and archive; the parent Requirement remains the human-facing
business/progress object.

## Development Backlog Project state

For managed tasks, publication reconciles an exact reviewable PR to `In review`, and terminal finish reconciles `Done` only after GitHub merge/direct delivery plus required local synchronization. Ordinary CI waiting remains `In review`.

Use `python3 scripts/managed_project_status.py block --reason "..."` only for a genuine external/human stop, `resume` after it clears, and `status --json` for read-only recovery evidence. These commands require GitHub Projects read/write authorization (`gh auth refresh -s project`). Quick tasks without managed provenance do not mutate the Development Backlog Project.

## Selective goal definition

Refine a goal before OpenSpec or managed-task authoring only when the user explicitly requests goal-backed work, or when a non-trivial request is materially unclear about its intended outcome or success evidence. Do not require goal creation for an ordinary concrete quick or implementation task.

A usable goal states the concrete outcome, verification evidence, a meaningful quantitative or binary success threshold, relevant scope bounds, and the condition that should stop work for clarification. If a missing choice could change the intended result, ask one concise question instead of inventing the requirement.

For an explicit goal-backed request, use supported native goal state through `/goal` or runtime-native goal tools when available, and inspect any active goal before creating a duplicate or conflicting one. Include a token budget only when the user explicitly requests one. A fuzzy request that the user did not ask to make goal-backed receives transient natural-language refinement, not implicit durable goal state. If native goal state was explicitly requested but is unavailable, perform an explicitly transient refinement or report the limitation; never claim that `create_goal` succeeded or that an active goal exists when the runtime cannot prove it.

Goal refinement creates no goal file, backlog entry, decision log, resume artifact, or competing implementation plan. For managed work, the refined outcome informs the Issue/OpenSpec package; after materialization, that package remains canonical.

## ADD -> Intents pre-authoring pipeline

For a business requirement that implies a genuine system-design delta (new/changed capabilities, boundaries, contracts, data ownership, invariants, security/trust concerns, or material non-functional behavior), the opt-in `add-intents` capability inserts two bounded pre-authoring stages ahead of OpenSpec proposal authoring: an Architecture Design Delta (ADD) against the current accepted system, then atomic Intent decomposition of the approved ADD. A clear bounded change with no useful design delta skips this and goes straight to normal task intake. See [dev-platform/capabilities/add-intents.md](../../dev-platform/capabilities/add-intents.md) for the full contract, gates, and `scripts/add_intents.py` usage; ADD/intents remain bounded pre-authoring evidence, never a second backlog or implementation contract.

`scripts/orchestrate_pre_authoring.py` sequences snapshot build/reuse (`scripts/project_evidence.py`), the ADD/Intents stages above, and OpenSpec handoff into one resumable `status`/`record-decision` surface: it re-validates the actual artifact files on every call, so a fresh stage is reused after a restart and an upstream mutation invalidates only its dependent downstream stages, without a second stateful lifecycle. `scripts/requirement_intake.py` binds a human-facing business Requirement Issue (`type:requirement`, business language only, no OpenSpec) to that orchestrator, and later links each resulting internal managed OpenSpec Issue back to it (`type:internal-change`) with read-through status aggregation from the existing Development Backlog Project — the Requirement stays the one thing a human normally manages.

## Central source dogfood lifecycle

For ordinary work in this central repository, use the committed source contract in `.dev-platform.toml` and its lifecycle adapter. Do not assemble a manual branch/worktree/PR flow. A managed task is imported first, then its sole untracked package is transferred into the isolated task worktree:

```bash
python3 scripts/start_managed_task.py owner/repo#N
cd .claude/worktrees/<change>
python3 scripts/dogfood_task.py status
python3 scripts/dogfood_task.py reconcile
python3 scripts/dogfood_task.py finish
```

`managed_task.py owner/repo#N` alone refuses to run directly on this repository's own integration checkout (`harness_mode=platform`, `workflow_profile=multi-agent`) and points here instead; `start_managed_task.py` performs the same read-only package intake from outside that checkout, then creates/reuses the task worktree/branch itself. An active `openspec/changes/<change>/` directory that predates provenance enforcement and carries no `.managed-task.json` needs a reviewed recovery that records its real source identity before it can resume through the normal managed lifecycle; never fabricate an Issue, delete the work, or bypass the guard — see [task-intake.md](task-intake.md#escalating-quick-work).

`status` is read-only and reports task-vs-authoritative-main freshness before costly validation; for a managed task it also carries a bounded, best-effort `source_issue_drift` field (whether the source Issue's title/body changed since authoring) as evidence only -- local OpenSpec stays canonical and is never rewritten from it. Run `python3 scripts/dogfood_task.py status --json` for the exact machine-readable recovery surface. If `status` reports `behind` or `diverged`, run `reconcile`: the explicit operation refuses dirty/provenance-ambiguous/changed-remote state and uses a normal merge only, never a rebase, force-push, reset or automatic stash. A reconciled head must rerun validation before `finish`, which delegates to the authoritative GitHub-backed publication/reconciliation lifecycle and is resumable; branch pushed, draft or open PR, and green checks are nonterminal states. Do not report source work as complete until GitHub reports the exact PR `MERGED` and local `main` has been reconciled (with cleanup warnings classified under the shared lifecycle policy).

If terminal reconciliation succeeds while the invoking shell still has the task worktree as its cwd, finish records exact worktree/branch/head cleanup metadata instead of deleting that cwd synchronously. This is a successful delivery with deferred housekeeping; from the surviving integration checkout, run the exact targeted recovery command printed by finish. Recovery verifies the recorded identity and current process/board/cleanliness state before removal, and is idempotent. Global cleanup is deliberately two-step: `python3 scripts/worktree_cleanup.py cleanup --all` previews the bounded candidate set, and `python3 scripts/worktree_cleanup.py cleanup --all --apply` performs the reviewed global action.

## Scope discipline and capabilities

Promote a rule/tool only when it is reusable across projects or a defined workflow profile. Keep application-domain rules, credentials, machine-local paths and one-off workarounds in the owning project.

A change to a downstream managed file must consider both new-project rendering and Copier update behavior for existing projects.

The shared lifecycle is composable. `light`, `standard`, and `multi-agent` profiles select capabilities rather than forking the template. GitHub sync/publish, checks, OpenSpec policy and release pinning are core; worktrees/board are multi-agent capabilities. In multi-agent admission, only a valid active board record with a proven worktree/branch identity can block a concrete file claim; degraded or terminal sibling records remain hygiene diagnostics, while unreadable or un-lockable board state fails closed.

## Validation

At minimum:

```bash
python3 -m compileall -q template/scripts scripts
python3 scripts/managed_projects.py --registry <operator-registry-path> validate
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

Record only high-signal friction: user correction, repeated failure, safety near-miss, undocumented invariant or excessive retries. Separate observation, evidence, hypothesis and proposal. Do not record secrets or routine successful sessions. When a correction or substantive failure shows missing or misread stable project context, record it with `--classification context-gap` and one bounded `--context-concern` (`product`, `domain`, `architecture`, `anti-pattern`, `example`, or `other`); the corresponding `docs/context/` destination is a candidate, not an automatic write. Tooling, CI, lifecycle, worktree, authentication, and process defects remain ordinary `process-friction`. Counts strengthen evidence only: they never edit context or create/start a managed task. When a finding concerns a specific participant, pass `--participant-role supervisor|executor`; the identity is read back from the current routing record rather than self-reported (see `docs/engineering/model-routing.md#execution-provenance`). Friction fingerprinting never includes model/provider, so the same recurring problem across different models still updates one issue.

### Post-task retrospective

Before non-trivial completion, run a distinct post-task retrospective -- not merely picking a checkpoint value. Review the task for user corrections, repeated substantive failures/retries, manual workarounds, safety near-misses, false premises, undocumented invariants, missing automation/documentation, tooling/auth/worktree/Git/OpenSpec/CI/lifecycle friction, avoidable repeated work, and problems noticed but left unresolved. A relevant user correction or repeated semantic failure may be a `context-gap` when it exposes stable project/domain knowledge that belongs in a bounded context destination; do not force ordinary agent mistakes or tooling/process defects into that category. Classify each candidate as already resolved in this task, already represented by an existing recorded event, or new and meaningful; record only the last class.

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
