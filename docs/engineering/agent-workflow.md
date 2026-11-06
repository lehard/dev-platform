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
Project card `Done` and closes its Issue; the idempotent
`python3 scripts/requirement_terminal.py reconcile --requirement owner/repo#N`
is a recovery command.
No `Requirement-Integration-Exception` is required for an ordinary single child.

Before terminal close run `python3 scripts/requirement_retrospective.py review-path --requirement owner/repo#N`, then review the whole Requirement path including successful overrides, manual workarounds and state changes, known issue recurrences, and material drift in other owners' state, and record its
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

### Lifecycle preflight

`select_checks.py --execute` and `finish_task.py` first run one cheap preflight (`scripts/lifecycle_preflight.py`) over every condition that could stop them after the expensive run: shared-workspace permissions on the task paths, the task's board claim and scope with scope overlap, freshness against main, and the project's `[settings] preflight_commands` (here the writer-guard baseline test). Each condition calls the gate's own function, prints `DEV_PLATFORM_PREFLIGHT: <condition>: passed|repaired|not-applicable|refused`, and all refusals are reported together before any test starts, each with its repair command. A path owned by the current OS account is repaired and listed as repaired; a path owned by another account is refused with the owner and the `chgrp`/`chmod` command. A lost board claim is restored with `agent_board.py start`. Every entry in `template/dev-platform/blocking-gates.toml` carries `preflight` (the condition that checks it ahead) or `no_preflight` (why it cannot be), and `tests/test_blocking_gates.py` fails for a missing or unresolvable entry.

## Selective goal definition

Refine a goal before OpenSpec or managed-task authoring only when the user explicitly requests goal-backed work, or when a non-trivial request is materially unclear about its intended outcome or success evidence. Do not require goal creation for an ordinary concrete quick or implementation task.

A usable goal states the concrete outcome, verification evidence, a meaningful quantitative or binary success threshold, relevant scope bounds, and the condition that should stop work for clarification. If a missing choice could change the intended result, ask one concise question instead of inventing the requirement.

For an explicit goal-backed request, use supported native goal state through `/goal` or runtime-native goal tools when available, and inspect any active goal before creating a duplicate or conflicting one. Include a token budget only when the user explicitly requests one. A fuzzy request that the user did not ask to make goal-backed receives transient natural-language refinement, not implicit durable goal state. If native goal state was explicitly requested but is unavailable, perform an explicitly transient refinement or report the limitation; never claim that `create_goal` succeeded or that an active goal exists when the runtime cannot prove it.

Goal refinement creates no goal file, backlog entry, decision log, resume artifact, or competing implementation plan. For managed work, the refined outcome informs the Issue/OpenSpec package; after materialization, that package remains canonical.

## ADD -> Intents pre-authoring pipeline

For a business requirement that implies a genuine system-design delta (new/changed capabilities, boundaries, contracts, data ownership, invariants, security/trust concerns, or material non-functional behavior), the opt-in `add-intents` capability inserts two bounded pre-authoring stages ahead of OpenSpec proposal authoring: an Architecture Design Delta (ADD) against the current accepted system, then atomic Intent decomposition of the approved ADD. A clear bounded change with no useful design delta skips this and goes straight to normal task intake. See [dev-platform/capabilities/add-intents.md](../../dev-platform/capabilities/add-intents.md) for the full contract, gates, and `scripts/add_intents.py` usage; ADD/intents remain bounded pre-authoring evidence, never a second backlog or implementation contract. The same file defines what belongs in an ADD (versus the Business Requirement, an existing contract and OpenSpec detail) and the one standard read-only Russian presentation of the ADD to a human (`add_intents.py render-add`), which adds no approval gate or human stop.

`scripts/orchestrate_pre_authoring.py` sequences snapshot build/reuse (`scripts/project_evidence.py`), the ADD/Intents stages above, and OpenSpec handoff into one resumable `status`/`record-decision` surface: it re-validates the actual artifact files on every call, so a fresh stage is reused after a restart and an upstream mutation invalidates only its dependent downstream stages, without a second stateful lifecycle. `scripts/requirement_intake.py` binds a human-facing business Requirement Issue (`type:requirement`, business language only, no OpenSpec) to that orchestrator, and later links each resulting internal managed OpenSpec Issue back to it (`type:internal-change`) with read-through status aggregation from the existing Development Backlog Project — the Requirement stays the one thing a human normally manages.

Snapshot-bound ADDs, intents and handoffs remain fresh across unrelated HEAD
movement when their bound source identities and evidence digests still match;
`prepared_against` remains provenance. A bound source change requires refresh.
After every recorded handoff digest is carried by a linked child Issue's exact
Requirement handoff marker, `execute_requirement.py advance` can use those
recorded handoffs for child ordering and terminal reconciliation without fresh
pre-authoring. Missing materialization and child contract conflicts still stop.

Lifecycle GitHub reads retry classified transient transport/server failures
with at most `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS` attempts (default 4 when unset; a
value that is not an integer of at least 1 is an error naming it), waiting
1, 2, 4 seconds between the default attempts; further delays cap at 8 seconds.
Non-transient failures return immediately, and mutations are never retried
automatically.

## Central source dogfood lifecycle

For ordinary work in this central repository, use the committed source contract `dev-platform/source-contract.toml` (installed as the untracked local `.dev-platform.toml`, which also carries operator-only sections) and its lifecycle adapter. Do not assemble a manual branch/worktree/PR flow. A managed task is imported first, then its sole untracked package is transferred into the isolated task worktree:

```bash
python3 scripts/start_managed_task.py owner/repo#N
cd .claude/worktrees/<change>
python3 scripts/dogfood_task.py status
python3 scripts/dogfood_task.py reconcile
python3 scripts/dogfood_task.py finish
```

A quick task needs no package: `python3 scripts/dogfood_task.py start <slug> --task "..." --scope "..."` creates its worktree, and the same `status`, `reconcile` and `finish` apply. `--scope` takes repository paths separated by commas or newlines; an entry with whitespace that is not an existing path is refused, because it would claim nothing and hide any overlap. A start refused on a hard overlap removes its worktree; if the overlap is verified safe, rerun it with `--acknowledge-overlap <reason>`.

**No work before start and routing.** Implementation of a managed child begins only after its `start` has created the task worktree and its route is recorded. This includes drafts: code, tests and scaffolding for a child are not prepared in advance in a sibling worktree, a scratch copy or the integration checkout. Reading and authoring the OpenSpec package are not implementation. Route preparation refuses a worktree whose task content already changed.

**Pending rollout at start.** Task start never merges a Dev Platform rollout PR, arms auto-merge on it or stops because it is open; only an explicit rollout merges it. `agent_doctor.py`, run first by start, reports an open rollout PR read-only.

`managed_task.py owner/repo#N` alone refuses to run directly on this repository's own integration checkout (`harness_mode=platform`, `workflow_profile=multi-agent`) and points here instead; `start_managed_task.py` performs the same read-only package intake from outside that checkout, then creates/reuses the task worktree/branch itself. An active `openspec/changes/<change>/` directory that predates provenance enforcement and carries no `.managed-task.json` needs a reviewed recovery that records its real source identity before it can resume through the normal managed lifecycle; never fabricate an Issue, delete the work, or bypass the guard — see [task-intake.md](task-intake.md#escalating-quick-work).

`status` is read-only and reports task freshness against main before costly validation. `reconcile` merges main. For a managed task `status` also carries a bounded, best-effort `source_issue_drift` field (whether the source Issue's title/body changed since authoring) as evidence only -- local OpenSpec stays canonical and is never rewritten from it. Run `python3 scripts/dogfood_task.py status --json` for the exact machine-readable recovery surface. If `status` reports `behind` or `diverged`, run `reconcile`: the explicit operation refuses dirty/provenance-ambiguous/changed-remote state and uses a normal merge only, never a rebase, force-push, reset or automatic stash. Before it pushes a new head to an armed PR it disables auto-merge, because GitHub keeps the request across a push; if that fails it pushes nothing. A reconciled head must rerun validation before `finish`, which delegates to the authoritative GitHub-backed publication/reconciliation lifecycle and is resumable; branch pushed, draft or open PR, and green checks are nonterminal states. `finish` follows an armed PR until GitHub reports `MERGED`. It stops non-zero on a failed required check (named), a PR that can no longer merge, or `ci_completion_minutes` from `.dev-platform.toml`, and that last stop prints the command to continue. Rerunning it resumes the same PR without repeating validation. Do not report source work as complete until GitHub reports the exact PR `MERGED` and local `main` has been reconciled (with cleanup warnings classified under the shared lifecycle policy).

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

The shared lifecycle is composable. `light`, `standard`, and `multi-agent` profiles select capabilities rather than forking the template. GitHub sync/publish, checks, OpenSpec policy and release pinning are core; worktrees/board are multi-agent capabilities. In multi-agent admission, only a valid active board record with a proven worktree/branch identity can block a concrete file claim; a task's factual scope is its own diff from its merge base with the observed `origin/<main>` (never the possibly stale local `main`), so files a reconcile brought in from main are not task scope, and an unobserved `origin/<main>` stops the scope gate instead of yielding an empty scope; a file declared generated in `[[generated_files]]` at the observed `origin/<main>` (such as the platform manifest) is never a hard overlap and stays visible as a soft one, while a declaration only on the task branch changes nothing and an unreadable declaration stops the gate; degraded or terminal sibling records remain hygiene diagnostics, while unreadable or un-lockable board state fails closed.

## Validation

`finish` selects and runs the local checks; run the same selection earlier with:

```bash
python3 scripts/select_checks.py --base origin/main --execute --task-evidence
```

The required `validate` job in `.github/workflows/ci.yml` runs the complete set on every PR head, and only it is merge authority. For a change to the managed registry also run `python3 scripts/managed_projects.py validate`.

`managed_projects.py` finds the registry through an enabled `[operator]` section of `.dev-platform.toml`; without one, pass `--registry <operator-registry-path>`.

The strict `openspec validate` is the command CI runs: `openspec_lifecycle.py check` does not include it, so the full check set and the docs check set run it, and a spec rule such as the requirement length limit fails before publication.

`check_ci_python.py` reads the Python version that the `validate` job of `.github/workflows/ci.yml` pins. When the local `python3` has another minor version, it compiles the sources with `python<major.minor>` of the CI version and fails on a compile error; an unreadable CI version or a missing or misreporting interpreter of that version is refused naming both versions. It catches compile-time errors only (for example the Python 3.11 limit on statically nested blocks), not runtime behaviour differences; required CI stays the merge gate. When Copier is available, render the template and compile/run the generated doctor. For Git lifecycle changes, exercise temporary local/bare remotes so fetch/sync/direct-publish safety is tested.

The selection follows the change: a semantic-preserving `AGENTS.md`/`docs/**`/OpenSpec-prose/`template/AGENTS.md.jinja` change gets bounded structure/link/anchor/render checks, while any change under `scripts/**`, `template/scripts/**` or `tests/**` (or any other Python file), an unknown or ambiguous path, and a control-plane (selector/CI/lifecycle) path run the `full_commands` of `dev-platform/checks.toml` without its `ci_only_commands`. Here that setting lists `run_test_groups.py --all`, so such a change runs the fast full commands plus the affected tests below, and the suite runs in `validate`. Run the suite locally with `python3 scripts/select_checks.py --mode protected-full --execute`. A local result never replaces the protected-full result required for a PR.

`ci_only_commands` also works in a project, but it is off unless the project's `dev-platform/checks.toml` sets it. The selector refuses it without `protected_main=true`, `publish_mode=pr`, `pr_merge_mode=auto` and GitHub, because only then does a required check gate every merge.

The changed-file set comes from `--changed-file`, an explicit `--base`, or, on a task branch without either, `origin/<main_branch>` (printed as the base used). There is no previous-commit fallback: on the main branch or a detached HEAD without `--base` or `--changed-file`, and when `git diff` fails, `select_checks.py` stops before any check runs and names the cause. The central wrapper resolves the same base before running the selector.

When `[settings] affected_precheck = true` (enabled in this repository), that run is preceded by an affected-test precheck: the test modules that directly import or name a changed Python file run first, inside their canonical groups, and a failure stops before the remaining commands. A precheck whose runner reports no usable aggregate (`unavailable`) stops the same way, named as unavailable, instead of continuing with the full set. Run the same feedback manually with `python3 scripts/run_test_groups.py --changed-file <path> [--changed-file <path> ...]`. Precheck results are recorded separately as `affected_precheck` feedback, and the evidence names what `left_to_required_ci`; the complete set in `validate` remains the merge authority. Tests register platform modules only through `tests/_platform_modules.py` so a test process holds one instance per module; `test_platform_module_identity` guards this.

## Machine validation pool

Several agents on one machine can start full validation at once; parallelism is capped only inside a single run, so N runs use N times the workers and timeout-sensitive tests then fail from contention. `machine_pool.py` is an opt-in, machine-wide counting pool that serializes that load. It is off unless the machine opts in: with `DEV_PLATFORM_MACHINE_POOL` unset, each top-level heavy run prints `DEV_PLATFORM_MACHINE_POOL: not configured` and runs unpooled.

**Configuration.** `DEV_PLATFORM_MACHINE_POOL` names an absolute machine-local TOML file (keep it outside every checkout) with exactly these keys:

```toml
directory = "/var/tmp/dev-platform-pool"   # existing absolute directory shared by every participating account
tokens = 8                                  # positive integer: total tokens on this machine
wait_timeout_seconds = 3600                 # positive integer: give up and fail after this wait
max_load_per_cpu = 1.5                      # positive number: admit only while load average (1 min) / CPUs <= this
min_available_memory_mb = 4096              # positive integer: admit only while available memory >= this
```

Missing or unknown keys, wrong types, a missing file, or a missing or unwritable directory fail explicitly, naming the key or path. Available memory is Linux `MemAvailable` or, on macOS, `vm_stat` free + inactive + speculative pages. On macOS admission also needs the kernel memory pressure level (`sysctl -n kern.memorystatus_vm_pressure_level`) to be normal: at warn or critical the run waits, because inactive pages still count as available while swap is nearly full. On any other platform, or when a value cannot be read or is unknown, the run fails instead of assuming enough memory.

**Multi-account setup.** Agents under different OS accounts must see the same configuration and directory. Create the directory once, writable by every participating account (for example group-writable with the setgid bit under a shared group, or world-writable when every account on the machine is trusted; do not set the sticky bit, because waiters remove other accounts' dead tickets), and export `DEV_PLATFORM_MACHINE_POOL` in each account's agent environment. Slot, ticket and queue files are created readable and writable for other accounts regardless of umask; a permission error fails naming the file. An agent whose environment lacks the variable runs unpooled and prints the `not configured` line, so the gap is visible.

**How a run is admitted.** A heavy run holds `weight` tokens, where `weight` is its test parallelism (`DEV_PLATFORM_TEST_JOBS` or the automatic cap) bounded by `tokens`. A `select_checks.py --execute` selection whose every command is labelled `configuration` or `syntax` in `evidence_types`, with no affected-test precheck, holds one token; an unlabelled or `test` command keeps the full weight. `select_checks.py --execute`, `run_test_groups.py` (`--all`, `--group`, `--changed-file`) and Requirement full-candidate validation each acquire once per top-level run. Waiting runs take a ticket in `directory/queue`; only the head ticket may acquire, all or nothing, and only while load, memory and (on macOS) memory pressure admit it; ticket creation and the head's admission are serialized by `directory/admission.lock` (never waited on: a busy lock is retried on the next poll within the wait timeout), so the head decision never uses a stale queue. Order is by class, then arrival: `finalize` (lifecycle finalization and Requirement integration, via `DEV_PLATFORM_CHECK_CLASS=finalize`) before `development` (the default when the variable is absent); any other class value fails. Tokens are kernel `flock` leases on `directory/slot-<i>.lock` passed to child processes, so they are released only when the run and every child it started have exited, including after SIGKILL; a dead waiter's ticket is removed by the next waiter. The lease is exported as `DEV_PLATFORM_MACHINE_POOL_LEASE`: a nested run (finish, selected checks, test groups) reuses it and acquires nothing, and the test runner never exceeds the lease weight.

**Visibility and failure.** A waiting run prints, at start and every 60 seconds, `DEV_PLATFORM_MACHINE_POOL: waiting, blocked by <blocker>` first — the queue, load, available memory, memory pressure, tokens or the admission lock, with the current value and threshold — and then the tokens it needs and how many are free, its queue position and who holds the tokens (account, project, branch, class, age). Free tokens with a load blocker therefore read as load, not as a token shortage. After `wait_timeout_seconds` it fails naming the holders; it never runs outside the pool. A process that hangs keeps its tokens, so the waiters fail visibly naming it rather than starting. `python3 scripts/machine_pool.py status` is read-only and prints the configuration, holders, waiters (and dead tickets awaiting removal), the current load per CPU, available memory and memory pressure, the head waiter's blocker in the same terms, and the heavy-run weight of the calling environment with how many such runs fit and how many tokens stay idle; it warns when `tokens` is not a multiple of that weight.

**Sizing.** Choose `tokens` as the number of heavy runs that should run at once times the weight of one run, and set that weight with `DEV_PLATFORM_TEST_JOBS` in every participating agent environment (the automatic cap is `min(4, logical CPUs - 1)`, which rarely divides `tokens`). Keep the total between the physical and the logical core count, because each test worker starts further subprocesses. Set `min_available_memory_mb` to leave headroom after memory reserved for VMs such as Docker Desktop, and `max_load_per_cpu` from a measurement of the chosen number of concurrent runs on that machine. Example: 4 physical / 8 logical cores and 16 GB with a Docker VM limit near 8 GB run two heavy runs of 3 workers: `tokens = 6`, `DEV_PLATFORM_TEST_JOBS=3`.

**Mixed releases.** Projects on different platform releases on one machine share the same configuration file, queue and tokens: the configuration keys and the slot, ticket and lease formats do not change. A release before this pool contract update keeps its own weight and memory check until the project is updated; it also honours `DEV_PLATFORM_TEST_JOBS`, so setting the variable aligns its weight too.

## Friction routing

Raw friction evidence stays machine-local. Record high-signal events through `scripts/agent_friction.py`; the normal path automatically upserts a bounded sanitized, fingerprinted process issue in the configured project or platform repository. Retry failure is durable and non-blocking for safe delivery. Process issues are evidence only: the periodic Process Health Review must never create managed tasks, OpenSpec, implementation PRs, or code changes.

If finish is blocked because an explicitly linked historical process Issue is no longer readable, status retains the exact merged PR fact and reports terminal reconciliation as pending. After confirming the reference is genuinely absent, record a narrow disposition from the managed task worktree with `python3 scripts/managed_task.py dispose-process-evidence --reference owner/repo#N --reason "..."`, then rerun finish. The command requires a definitive HTTP 404 after verifying access to the evidence repository and writes an auditable comment on the managed source Issue. A permission, authentication, or transport failure cannot authorize disposition. Open or readable evidence follows the normal resolution path.

A routing failure leaves the event pending in the local state. Ordinary `start`, `doctor`, `finish` and `advance` never retry or wait on routing; the explicit `python3 scripts/agent_friction.py route-pending` retries pending events and reports routed, failed and withheld counts. Coordinator lifecycle events (`coordinator-review-repair`, `coordinator-retry`, `coordinator-integration-repair`, `lifecycle-blocked-escalation`, `lifecycle-validation-failure`, or any coordinator-attributed event) carry a bounded `reason` and a `candidate` (task branch, PR number when one exists, head); the routed body shows both. The publication coordinator takes the reason from the transition's red gate and fails the transition when no named red gate explains it (a `blocked-retryable` without a red gate only waits on exact-head required checks and records no event); `record` for these categories requires `--reason` and `--candidate-task/--candidate-head`. A coordinator event without a reason or candidate is never published: its route is recorded as `withheld` naming the missing field and is not retried.

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

One root cause keeps one open friction issue. An issue may carry several fingerprint markers, and routing attaches an event to the open issue carrying its marker. An event left in `candidate` state is resolved explicitly with `agent_friction.py resolve-candidate --id <event> (--same-root owner/repo#N | --new-root) --reason TEXT`; `--same-root` records the event as an occurrence of N and appends its marker to N. Already open duplicates are consolidated with `agent_friction.py merge-roots --into owner/repo#N --duplicate owner/repo#M [...] --reason TEXT`. A fix closes the friction records it resolves by declaring `Fixes-Friction: owner/repo#N` lines (comma or space separated, full same-repository form) in a commit message, its PR body or its OpenSpec `proposal.md`; a quick task uses the commit trailer, and `review-path` reminds of it; when the PR merges, `.github/workflows/friction-close-on-merge.yml` runs `agent_friction.py close-fixed` and closes them. A malformed, cross-repository or non-friction reference fails the run, and a record without a reference is never closed automatically.

Record only high-signal friction: user correction, repeated failure, safety near-miss, undocumented invariant or excessive retries. Separate observation, evidence, hypothesis and proposal. Do not record secrets or routine successful sessions. Routing removes a bare `#N` and any Issue reference to another repository from public text, because it cannot tell a private Backlog number from a public one; name a public Issue of this repository as `owner/repo#N`. When a correction or substantive failure shows missing or misread stable project context, record it with `--classification context-gap` and one bounded `--context-concern` (`product`, `domain`, `architecture`, `anti-pattern`, `example`, or `other`); the corresponding `docs/context/` destination is a candidate, not an automatic write. Tooling, CI, lifecycle, worktree, authentication, and process defects remain ordinary `process-friction`. Counts strengthen evidence only: they never edit context or create/start a managed task. When a finding concerns a specific participant, pass `--participant-role supervisor|executor`; the identity is read back from the current routing record rather than self-reported (see `docs/engineering/model-routing.md#execution-provenance`). Friction fingerprinting never includes model/provider, so the same recurring problem across different models still updates one issue.

### Problem and decision history

Three rules keep the history of repeated attempts and owner choices reachable without a separate registry ([DEC-0004](../decisions/0004-main-advance-revalidation.md) shows them applied):

1. **Problem record.** When work is a second or later attempt at the same problem, the Requirement names the problem's friction root issue (the one open issue for that root cause, see above) in `Context`. After delivery the change appends a short entry to that root issue: which change, what it did, why the earlier attempts were not enough, and what stayed out of scope. Public entries use `BR-N` identities and public PR numbers, never private Backlog links.
2. **Decision record.** An owner choice between options, or a hard-to-reverse decision, is recorded in [`docs/decisions/`](../decisions/README.md) with the rejected options and revisit triggers. `design.md` links that record instead of quoting the choice.
3. **Look before proposing.** Before writing a proposal, search the related root issue and decision records and link the ones that apply in `proposal.md` (see [openspec-workflow.md](openspec-workflow.md#author-the-outcome-contract)).

Specs never carry this rationale, and decision records never restate requirements.

### Post-task retrospective

Before non-trivial completion, run `python3 scripts/agent_friction.py review-path` to inspect the bounded checklist and task-attributed signals already in the local friction log. Then run a distinct post-task retrospective over the actual task path: inspect non-default/override flags used, successful manual workarounds and state changes, known process issues encountered again, and material drift observed in operator-owned or other lifecycle state. A successful workaround is still a candidate; an already open issue does not dispose of a new recurrence. Record meaningful occurrences with `agent_friction.py record --task <branch>` and the applicable `--trigger` value (`manual-workaround`, `nondefault-override`, `known-recurrence`, or `observed-drift`); repeat `--trigger` when needed. The existing router adds a new occurrence to a matching open process issue. Harmless deviations and routine commands are not friction. Do not copy raw shell history or secrets into the review note.

Review the task for user corrections, repeated substantive failures/retries, manual workarounds, safety near-misses, false premises, undocumented invariants, missing automation/documentation, tooling/auth/worktree/Git/OpenSpec/CI/lifecycle friction, avoidable repeated work, and problems noticed but left unresolved. A relevant user correction or repeated semantic failure may be a `context-gap` when it exposes stable project/domain knowledge that belongs in a bounded context destination; do not force ordinary agent mistakes or tooling/process defects into that category. Classify each candidate as already resolved in this task, already represented by an existing recorded event, or new and meaningful; record only the last class.

The retrospective also reads the current task's existing high-signal `lifecycle-*` failure records and recorded workaround/override/recurrence/drift signals from the friction log. It does not add a task-outcome database: a lifecycle failure must be classified as `resolved-in-task`, `already-recorded`, or `new-recorded` before the checkpoint can succeed. Clean tasks have no such records and retain the one-command `none` path.

```bash
python3 scripts/agent_friction.py checkpoint --result none --review-note "Reviewed actual task path and found no meaningful workaround, override, recurrence or drift"
python3 scripts/agent_friction.py checkpoint --event <id> [--event <id> ...] --review-note "Reviewed actual task path and linked meaningful occurrences"
python3 scripts/agent_friction.py checkpoint --result none --review-note "Reviewed actual task path and found no meaningful workaround, override, recurrence or drift" --disposition <event-id>=resolved-in-task|already-recorded|expected-behavior
```

Event attribution: `record` takes the task from `--task`, otherwise the current task branch; an event recorded on the integration branch or an unknown or detached branch is outside any task and is marked `no-task` (a legacy task-less event recorded on such a branch is read the same way). A `no-task` event is never a signal of, nor a block for, any task or Requirement retrospective; `review-path` and checkpoint output list recent ones as `no_task_events`, and they stay in the shared friction review. The review also recovers legacy events whose `task` is empty through their recorded `branch` or source issue without rewriting them (`inferred_attribution` in `review-path`). Only a recent event with no task, no usable branch or source issue and no `no-task` classification is `ambiguous_attribution`: it is neither assigned to this task nor hidden, and the manual task and Requirement `checkpoint` refuse until it is resolved. An operator who knows the owning task records `agent_friction.py attribute --id <event> --task owner/repo#N --reason "..."`, and one who knows it belongs to no task records `agent_friction.py attribute --id <event> --no-task --reason "..."`: an append-only attribution next to the log that leaves the event itself unchanged, fails for an unknown event id, and refuses to attribute one event to a second task or to both a task and no task. An automatic `no-task` classification can still be overridden by an explicit task attribution. Coordinator retrospective jobs block only on unattributable events recorded at or after the proven start of their scope (the creation of a Requirement's Issue); an unprovable start blocks.

Every mandatory signal (high-signal `lifecycle-*` failure, or a recorded workaround, override, recurrence or drift event) must be linked with `--event` or classified with `--disposition <event-id>=resolved-in-task|already-recorded|expected-behavior`; the recorded event is the evidence. A `known-recurrence` occurrence can only be linked. An unreadable or partial evidence source (`evidence_sources` in `review-path`) is not a clean result: repair it or accept it explicitly with `--accept-gap friction-log`.

`review-path` prints a short shared `template`: what happened and on what evidence; confirmed cause kept apart from hypothesis (unknown is acceptable); fix kept apart from workaround; repeats and remaining problems; the action with a verifiable result or why none is needed. A project may add at most five `[[question]]` entries (`text`, optional `paths` globs) to its own `dev-platform/retrospective.toml`; they are shown only when the changed files match and never replace the shared template. A missing or invalid file leaves the shared path working. A clean task stays one `checkpoint --result none` command.

`--result none` is valid only after the factual path review recorded a short `--review-note` and found nothing new and every mandatory signal is linked or has an explicit disposition. Referencing its recorded event is the `new-recorded` disposition; `--disposition` (alias `--lifecycle-disposition`) covers the resolved/already-recorded/expected-behavior cases. The checkpoint binds to the current branch and to a content proof of the task's own diff without files declared in `[[generated_files]]`; `finish` checks it before the rest of its preflight; `require_checkpoint` rejects it as stale once task-owned content changes, while a merge-only reconcile whose `main` side touched no task path, or only declared generated files, keeps it valid (a fresh retrospective is otherwise required), rejects a checkpoint referencing an unknown event id, and rechecks for newly unexplained mandatory signals. A missing/stale/unclassified checkpoint blocks `finish_task.py` with an actionable instruction -- it never invents `none`.

## Completion

Commit the verified active change and run finish. Finish runs the independent review when `[independent_review] enabled = true`, calls shared `finalize_change`, commits the archive, and then publishes. Requirement advance uses the same executor for a ready child before recording its ready receipt. Developers do not run an archive command. Finalization reuses selected-check evidence by the finish rule and prints the decision.

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

Whenever `finish` would run the selected checks it first decides, by one rule, whether recorded evidence already covers them and prints `DEV_PLATFORM_CHECK_REUSE` with the decision and reason: the evidence succeeded, every command of the selection required now ran successfully, and its task-content proof is equivalent to the current one (equal own diff; across a base move the old base is an ancestor of the new one and main touched no task path). A clean merge or rebase on an advanced `main` therefore does not repeat the local run; required CI on the exact PR head stays the merge gate. A managed task reuses its archive evidence; a quick task reuses machine-local evidence that `select_checks.py --execute --task-evidence` writes to its worktree's git directory (`finish` passes `--task-evidence` when it runs a quick task's checks).

While the managed change is active, `select_checks.py --execute` refuses before any command when `--evidence` is missing or the change is not archive-ready. Record evidence with `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/<change>/automated-checks.json`, record semantic verification, commit, then run `finish`.
