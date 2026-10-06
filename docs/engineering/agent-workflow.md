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
ceremonial OpenSpec. This includes a small regression repair when an accepted
spec or equivalent durable contract unambiguously establishes the expected
behavior. Record that contract and proportionate regression evidence: where a
reasonable test seam exists, show the defect before repair, show the check
passing after, and rerun the original failure path. Otherwise, state the
limitation and actual alternative check truthfully. If it expands into a
material behavior, architecture, compatibility, data-contract, or scope
change, stop implementation and enter the appropriate non-trivial intake route
before continuing.

**Fresh non-trivial execution / execute a Business Requirement.** By default,
material business/product work is requirement-first. Create/reuse the
Requirement if necessary, then run:

```bash
python3 scripts/requirement_intake.py start --requirement owner/repo#N
python3 scripts/orchestrate_pre_authoring.py --id requirement-N status
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

Before terminal publication, run `python3 scripts/requirement_retrospective.py review-path --requirement owner/repo#N`, then review the whole Requirement path including successful overrides, manual workarounds and state changes, known issue recurrences, and material drift in other owners' state, and record its
bounded parent retrospective through `scripts/requirement_retrospective.py`.
Use `--result none` only after checking accepted intent, pre-authoring,
decomposition, child interaction and delivery and finding no new meaningful
friction. Record new findings with `scripts/agent_friction.py record --task
owner/repo#N` and reference their ids with `--result findings --event <id>`.
The parent checkpoint is a machine-local completion receipt, not another
backlog or task state. Missing or stale evidence blocks parent `Done`.
Technical children still run their own post-task retrospectives.

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

#### Requirement metrics

To judge a harness change by its end-to-end effect, use the read-only metrics
report for one Requirement, or compare several side by side:

```bash
python3 scripts/requirement_metrics.py report --requirement owner/repo#N [--format text] [--offline]
python3 scripts/requirement_metrics.py aggregate --requirement owner/repo#N --requirement owner/repo#M
python3 scripts/requirement_metrics.py aggregate --closed-since YYYY-MM-DD
```

It composes existing sources only: the Requirement and child Issues,
pre-authoring evidence, managed provenance, routing/execution records,
archived verification, automated-check and independent review evidence, the
published PR commit history, publication labels, GitHub Actions runs, the
friction log and, for Claude Code, local session transcripts (counters only,
`--claude-projects-dir` overrides the default location). Every value is
`{value, status, sources}` with status `measured`, `derived`, `partial` or
`unknown`; missing evidence stays unknown and history rebuilt from published
commits (review rounds and their rerun causes, validation cycles) is a partial
lower bound, never zero or an estimate. `--offline` skips remote reads and
marks those sections unknown. Runtime-specific usage and session counters stay
keyed by runtime. The output never contains prompts, transcript text, tool
payloads, finding text or friction prose. The report writes nothing, produces
no score and changes no routing, budget or lifecycle policy; acting on it
requires its own managed change.

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

### Source publication queue

In `dev-platform`, after the queue workflow reaches `main`, `dogfood_task.py finish` admits the exact verified PR to a GitHub-backed ordered queue. The PR comment records its admission and order; `publication:queued`, `publication:active`, and `publication:blocked` labels show its current phase. `python3 scripts/dogfood_task.py status` reports the queue position and reason. A GitHub Actions coordinator handles one PR at a time and wakes on admission and every five minutes. Waiting task agents can leave their independent worktrees and resume `finish` after the exact PR merges; `finish` then completes local and managed-task reconciliation.

The coordinator uses the Dev Platform GitHub App token. The App must be able to read PRs, write PR comments and labels, update PR branches, and merge into protected `main`. If an admission or coordinator mutation is denied, inspect the `Dev Platform publication queue` workflow run and repair the App permission or credential. The worker does not bypass branch protection or required `validate` checks.

The coordinator workflow wakes on the label through `pull_request_target`, so every trigger runs the workflow and worker from the default branch and never executes PR-controlled content with the App token. That token is scoped to this repository with only contents write and pull requests write. If a mutation is denied for a missing permission, widen the token deliberately rather than carrying extra permissions by default.

When a PR receives `publication:blocked`, read the reason in `dogfood_task.py status` and the latest queue marker comment. A changed task head, overlapping main path, conflict, or failed check requires agent review and correction. After a new task commit, run the normal validation and `finish` again; this creates a new admission slot on the same PR after the prior block. A stale unchanged head remains blocked. `python3 scripts/publication_queue.py worker` can also be run by an authorized operator to retry a waiting queue head; the scheduled workflow normally handles recovery. Do not edit queue comments or labels by hand.

Each coordinator transition also publishes a `dev-platform-publication-queue:v2` handoff record (state, exact head, task identity, gate bindings, red gate, items not re-verified, attempts, next job) and projects it into one `lifecycle:<state>` label. State is derived from the latest valid v2 record for the exact PR head plus labels and required checks; a record for an older head contributes no gates, a malformed record blocks with its reason, and v1 admissions still read as `ready`/`integrating`. A transition re-observes the head and latest record first, carries gates and attempts forward and is not re-published when nothing changed; the worker skips a candidate whose current-head record is owned by review, repair, finalization, escalation or integration repair, and integrates the next one. Only records written by proven repository writers (owner, or members/collaborators with write permission) or the configured coordinator App count: the workflow exports its App slug as `DEV_PLATFORM_COORDINATOR_APP`, and a local reader sets `[publication] coordinator_app` in the external operator config (or project config). `python3 scripts/publication_queue.py status --pr N` or `--requirement owner/repo#N` (add `--json` for machine output) renders the state, red gate, attempts and next action read-only from any checkout.

### Lifecycle workers

`python3 scripts/lifecycle_workers.py work-next --repo owner/repo --kinds review,repair [--dry-run]` lets any worker (local, server or agent session) claim one job the coordinator published for a PR: review, repair, integration-repair, finalize, retrospective, terminal-reconciliation or cleanup, each bound to the exact head, task identity and attempt. A claim is a trusted `dev-platform-lifecycle-claim:v1` PR comment with a time limit; the earliest valid unexpired claim for that job and head wins by comment order, a worker re-reads after posting and abandons if it lost, expired or head-stale claims are reclaimable, and a result for a different head is discarded. LLM processes run in a disposable checkout with `stdin` closed and with GitHub tokens, credential helpers and SSH agents removed from the environment. A write result (repair and integration-repair only; review has no write path) is accepted only as a fast-forward from the expected head within candidate paths with no workflow or lifecycle-evidence edits, and the harness alone pushes it with `--force-with-lease` bound to the expected head. `work-next --run --llm-command "<cmd>" --source <repo> --branch <branch> --allow <path>` executes the claimed job: the LLM works in its own disposable checkout; the harness re-reads the PR head (a moved head discards the result), then validates in a separate fresh harness clone that fetches only the result commit and performs the only push from there, so hooks, remotes or credential settings planted in the LLM checkout are never used. A compact `dev-platform-lifecycle-result:v1` comment records the outcome. LLM processes run with a scratch `HOME`/`XDG_*` and an empty `GH_CONFIG_DIR`; only files named with `--llm-home-file` (the LLM CLI's own login, e.g. `.codex/auth.json`; never `.config/gh` or `.ssh`) are copied in. An OS credential store such as the macOS Keychain cannot be hidden without an OS sandbox: on an operator workstation that remains a residual risk, so prefer hosted workers without operator credentials for untrusted content. Merge authority stays with the coordinator.

Use `python3 scripts/managed_project_status.py block --reason "..."` only for a genuine external/human stop, `resume` after it clears, and `status --json` for read-only recovery evidence. These commands require GitHub Projects read/write authorization (`gh auth refresh -s project`). Quick tasks without managed provenance do not mutate the Development Backlog Project.

## Selective goal definition

Refine a goal before OpenSpec or managed-task authoring only when the user explicitly requests goal-backed work, or when a non-trivial request is materially unclear about its intended outcome or success evidence. Do not require goal creation for an ordinary concrete quick or implementation task.

A usable goal states the concrete outcome, verification evidence, a meaningful quantitative or binary success threshold, relevant scope bounds, and the condition that should stop work for clarification. If a missing choice could change the intended result, ask one concise question instead of inventing the requirement.

For an explicit goal-backed request, use supported native goal state through `/goal` or runtime-native goal tools when available, and inspect any active goal before creating a duplicate or conflicting one. Include a token budget only when the user explicitly requests one. A fuzzy request that the user did not ask to make goal-backed receives transient natural-language refinement, not implicit durable goal state. If native goal state was explicitly requested but is unavailable, perform an explicitly transient refinement or report the limitation; never claim that `create_goal` succeeded or that an active goal exists when the runtime cannot prove it.

Goal refinement creates no goal file, backlog entry, decision log, resume artifact, or competing implementation plan. For managed work, the refined outcome informs the Issue/OpenSpec package; after materialization, that package remains canonical.

## ADD -> Intents pre-authoring pipeline

For a business requirement that implies a genuine system-design delta (new/changed capabilities, boundaries, contracts, data ownership, invariants, security/trust concerns, or material non-functional behavior), the opt-in `add-intents` capability inserts two bounded pre-authoring stages ahead of OpenSpec proposal authoring: an Architecture Design Delta (ADD) against the current accepted system, then atomic Intent decomposition of the approved ADD. A clear bounded change with no useful design delta skips this and goes straight to normal task intake. See [dev-platform/capabilities/add-intents.md](../../dev-platform/capabilities/add-intents.md) for the full contract, gates, and `scripts/add_intents.py` usage; ADD/intents remain bounded pre-authoring evidence, never a second backlog or implementation contract.

`scripts/orchestrate_pre_authoring.py` sequences snapshot build/reuse (`scripts/project_evidence.py`), the ADD/Intents stages above, and OpenSpec handoff into one resumable `status`/`record-decision` surface: it re-validates the actual artifact files on every call, so a fresh stage is reused after a restart and an upstream mutation invalidates only its dependent downstream stages, without a second stateful lifecycle. `scripts/requirement_intake.py` binds a human-facing business Requirement Issue (`type:requirement`, business language only, no OpenSpec) to that orchestrator, and later links each resulting internal managed OpenSpec Issue back to it (`type:internal-change`) with read-through status aggregation from the existing Development Backlog Project — the Requirement stays the one thing a human normally manages.

Snapshot-bound ADDs, intents and handoffs remain fresh across unrelated HEAD
movement when their bound source identities and evidence digests still match;
`prepared_against` remains provenance. A bound source change requires refresh.
After every recorded handoff digest is carried by a linked child Issue's exact
Requirement handoff marker, `execute_requirement.py advance` can use those
recorded handoffs for child ordering and terminal reconciliation without fresh
pre-authoring. Missing materialization and child contract conflicts still stop.

Lifecycle GitHub reads retry classified transient transport/server failures
with at most `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS` attempts (default 4), waiting
1, 2, 4 seconds between the default attempts; further delays cap at 8 seconds.
Non-transient failures return immediately, and mutations are never retried
automatically.

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

## Disposable repository sandboxes

For a temporary local clone used by a pilot or other destructive experiment,
use `python3 scripts/disposable_repository_sandbox.py create <source> <sandbox-root> <name>`.
Run `verify <sandbox-root> <name>` before an external recursive operation, or
use `cleanup <sandbox-root> <name>` to verify and remove the helper-owned copy.
The helper refuses hardlinked files, object alternates, linked Git metadata,
unowned copies and links beyond the exact copy. A failed check stops recursive
changes; do not retry with a best-effort `chmod` or `rm -rf`.

## Scope discipline and capabilities

Promote a rule/tool only when it is reusable across projects or a defined workflow profile. Keep application-domain rules, credentials, machine-local paths and one-off workarounds in the owning project.

A change to a downstream managed file must consider both new-project rendering and Copier update behavior for existing projects.

Opt-in application source permissions, external hook attachment and per-user
automation are documented in [local-workspace.md](local-workspace.md). The
operator-local policy is checked separately from platform shared state.

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

When `[settings] affected_precheck = true` (enabled in this repository), that full run is preceded by an affected-test precheck: the test modules that directly import or name a changed Python file run first, inside their canonical groups, and a failure stops before the expensive full set. Run the same feedback manually with `python3 scripts/run_test_groups.py --changed-file <path> [--changed-file <path> ...]`. Precheck results are recorded separately as `affected_precheck` feedback; the complete set still runs and remains the only validation evidence. Tests register platform modules only through `tests/_platform_modules.py` so a test process holds one instance per module; `test_platform_module_identity` guards this.

## Friction routing

Raw friction evidence stays machine-local. Record high-signal events through `scripts/agent_friction.py`; the normal path automatically upserts a bounded sanitized, fingerprinted process issue in the configured project or platform repository. Retry failure is durable and non-blocking for safe delivery. Process issues are evidence only: cloud triage/review must never create managed tasks, OpenSpec, implementation PRs, or code changes.

If finish is blocked because an explicitly linked historical process Issue is no longer readable, status retains the exact merged PR fact and reports terminal reconciliation as pending. After confirming the reference is genuinely absent, record a narrow disposition from the managed task worktree with `python3 scripts/managed_task.py dispose-process-evidence --reference owner/repo#N --reason "..."`, then rerun finish. The command requires a definitive HTTP 404 after verifying access to the evidence repository and writes an auditable comment on the managed source Issue. A permission, authentication, or transport failure cannot authorize disposition. Open or readable evidence follows the normal resolution path.

The periodic Process Health Review is advisory and read-only. Its dated report
records `reviewed_at`, the exact `main` SHA, and its previous-review boundary;
it reads bounded current Requirement parents, linked children, process issues
from pre-authoring or the parent retrospective, and merged-change context, clusters
symptoms by likely root cause, and verifies likely-resolved candidates against
current repository evidence. Clean children do not suppress earlier or
cross-child findings. Specialized review findings use the same friction router
and process-issue evidence, with no parallel improvement queue. It does not add ritual source-issue comments,
create work, or resolve source issues. Explicitly linked evidence is closed
only after the existing terminal merge, local reconciliation, and Project-Done
path succeeds.

Publish a new machine-local Process Health Review report with
`python3 scripts/shared_workspace.py publish-report --name YYYY-MM-DD-topic.md < report.md`.
The command uses the configured registered reports directory, creates only a
new basename, and verifies group read/write on its published file before
returning success. It refuses an existing report, path traversal, and symlinks.
For a correction to an existing report owned by the current writer, use
`shared_workspace.atomic_write_text` from `template/scripts` and then run
`python3 scripts/shared_workspace.py check`. Run that read-only check after
each review, including reports written by external editors; repair only files
owned by the current writer. New platform script functions that create files
must pass the direct-writer CI guard or receive explicit review of the new
creation call and its declared output verification. An external editor is
outside the platform writer API, so its output remains subject to the check.

The weekly cloud Process Health Review is the routine cadence. Local friction
`pending`/`review` commands remain recovery and diagnostic surfaces rather than
actions required from each current task agent. `reconcile-process-labels` is a
bounded, idempotent recovery operation: it restores the configured `process`
label only on unmistakably router-generated open source issues.

Record only high-signal friction: user correction, repeated failure, safety near-miss, undocumented invariant or excessive retries. Separate observation, evidence, hypothesis and proposal. Do not record secrets or routine successful sessions. When a correction or substantive failure shows missing or misread stable project context, record it with `--classification context-gap` and one bounded `--context-concern` (`product`, `domain`, `architecture`, `anti-pattern`, `example`, or `other`); the corresponding `docs/context/` destination is a candidate, not an automatic write. Tooling, CI, lifecycle, worktree, authentication, and process defects remain ordinary `process-friction`. Counts strengthen evidence only: they never edit context or create/start a managed task. When a finding concerns a specific participant, pass `--participant-role supervisor|executor`; the identity is read back from the current routing record rather than self-reported (see `docs/engineering/model-routing.md#execution-provenance`). Friction fingerprinting never includes model/provider, so the same recurring problem across different models still updates one issue.

### Post-task retrospective

Before non-trivial completion, run `python3 scripts/agent_friction.py review-path` to inspect the bounded checklist and task-attributed signals already in the local friction log. Then run a distinct post-task retrospective over the actual task path: inspect non-default/override flags used, successful manual workarounds and state changes, known process issues encountered again, and material drift observed in operator-owned or other lifecycle state. A successful workaround is still a candidate; an already open issue does not dispose of a new recurrence. Record meaningful occurrences with `agent_friction.py record --task <branch>` and the applicable `--trigger` value (`manual-workaround`, `nondefault-override`, `known-recurrence`, or `observed-drift`); repeat `--trigger` when needed. The existing router adds a new occurrence to a matching open process issue. Harmless deviations and routine commands are not friction. Do not copy raw shell history or secrets into the review note.

Review the task for user corrections, repeated substantive failures/retries, manual workarounds, safety near-misses, false premises, undocumented invariants, missing automation/documentation, tooling/auth/worktree/Git/OpenSpec/CI/lifecycle friction, avoidable repeated work, and problems noticed but left unresolved. A relevant user correction or repeated semantic failure may be a `context-gap` when it exposes stable project/domain knowledge that belongs in a bounded context destination; do not force ordinary agent mistakes or tooling/process defects into that category. Classify each candidate as already resolved in this task, already represented by an existing recorded event, or new and meaningful; record only the last class.

The retrospective also reads the current task's existing high-signal `lifecycle-*` failure records and recorded workaround/override/recurrence/drift signals from the friction log. It does not add a task-outcome database: a lifecycle failure must be classified as `resolved-in-task`, `already-recorded`, or `new-recorded` before the checkpoint can succeed. Clean tasks have no such records and retain the one-command `none` path.

```bash
python3 scripts/agent_friction.py checkpoint --result none --review-note "Reviewed actual task path and found no meaningful workaround, override, recurrence or drift"
python3 scripts/agent_friction.py checkpoint --event <id> [--event <id> ...] --review-note "Reviewed actual task path and linked meaningful occurrences"
python3 scripts/agent_friction.py checkpoint --result none --review-note "Reviewed actual task path and found no meaningful workaround, override, recurrence or drift" --disposition <event-id>=resolved-in-task|already-recorded|expected-behavior
```

Event attribution: `record` takes the task from `--task`, otherwise the current task branch; an event recorded on the integration branch or an unknown branch is marked `unattributed`. The review also recovers legacy events whose `task` is empty through their recorded `branch` or source issue without rewriting them (`inferred_attribution` in `review-path`). Recent events that cannot be attributed at all appear as `ambiguous_attribution`; they are neither assigned to this task nor hidden.

Every mandatory signal (high-signal `lifecycle-*` failure, or a recorded workaround, override, recurrence or drift event) must be linked with `--event` or classified with `--disposition <event-id>=resolved-in-task|already-recorded|expected-behavior`; the recorded event is the evidence. A `known-recurrence` occurrence can only be linked. An unreadable or partial evidence source (`evidence_sources` in `review-path`) is not a clean result: repair it or accept it explicitly with `--accept-gap friction-log`.

`review-path` prints a short shared `template`: what happened and on what evidence; confirmed cause kept apart from hypothesis (unknown is acceptable); fix kept apart from workaround; repeats and remaining problems; the action with a verifiable result or why none is needed. A project may add at most five `[[question]]` entries (`text`, optional `paths` globs) to its own `dev-platform/retrospective.toml`; they are shown only when the changed files match and never replace the shared template. A missing or invalid file leaves the shared path working. A clean task stays one `checkpoint --result none` command.

`--result none` is valid only after the factual path review recorded a short `--review-note` and found nothing new and every mandatory signal is linked or has an explicit disposition. Referencing its recorded event is the `new-recorded` disposition; `--disposition` (alias `--lifecycle-disposition`) covers the resolved/already-recorded/expected-behavior cases. The checkpoint binds to the current branch and Git head; `require_checkpoint` rejects it as stale once new commits land (a fresh retrospective is then required), rejects a checkpoint referencing an unknown event id, and rechecks for newly unexplained mandatory signals. A missing/stale/unclassified checkpoint blocks `finish_task.py` with an actionable instruction -- it never invents `none`.

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

For coordinator-managed source candidates, `finish` ends at developer handoff,
with the change still active. Before finish, run selected checks with
`python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/<change>/automated-checks.json`,
record semantic verification, commit the candidate and evidence, then record
the developer friction checkpoint at that exact head. Finish publishes an exact-head PR, admits it as
`review-pending`, and releases the developer board claim without waiting for CI,
review or merge. This is developer completion; terminal delivery still requires
archive and confirmed merge. The worker entrypoint
`python3 scripts/lifecycle_workers.py work-next --repo owner/repo --kinds review --run`
launches the existing independent reviewer in an exact-head disposable checkout.
Repair workers use `--kinds repair --run --llm-command <writer> --allow <path>`
(repeat `--allow` for the bounded candidate scope). The harness supplies findings,
validates the commits and pushes them; changed content repeats review. Material
rejection proposals or three unsuccessful review rounds require human escalation.
Unavailable reviewer runtimes publish a new retryable review attempt automatically.
