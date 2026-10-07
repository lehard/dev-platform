# Managed task intake

This is the canonical, platform-owned contract for turning a user request into
work. `AGENTS.md` remains the short repository map; project/domain rules remain
project-owned. Read this document before authoring or executing non-trivial
work.

Its intent boundaries, managed representation, source-of-truth model, and
authoring STOP rules apply across conversation surfaces. Repository-local
agents use the commands below; ChatGPT Project follows the connected-GitHub
mechanics in [chatgpt-project-protocol.md](chatgpt-project-protocol.md) without
creating a separate task format.

## Intent boundary

- **Discuss**: inspect, design and compare. Do not create durable Backlog state.
- **Incubate / park**: preserve a potentially useful idea without accepting it
  for delivery. Use the repository-backed Incubator contract below; do not
  create a Requirement, managed task, or OpenSpec package.
- **Fix / add to Backlog**: an explicit recording request (for example
  `зафиксируй`, `добавь в бэклог`, `создай задачу`, `отправь в бэклог`)
  creates or updates a human-facing Business Requirement and stops. Fixation
  does **not** author OpenSpec, perform technical decomposition, start
  pre-authoring, start implementation, or change lifecycle status.
  `requirement_intake.py create` applies the checkout's configured
  `[development_backlog]` project label and the explicit or default priority
  to the Requirement, fails closed before creating anything when that routing
  cannot be resolved (mismatched Backlog repository, a target repository not
  configured in this checkout, or an unavailable label), and verifies both
  labels by reading the Issue back before reporting success. Success also
  requires **Project membership**: the configured `project_owner/project_number`
  must hold exactly one item for the Issue with an initialized Status. GitHub's
  built-in auto-add is only a fast path; `create` adds a missing item through
  the same Project authorization (idempotent, no duplicate), initializes an
  unset Status to `Backlog` without overwriting an existing one and confirms
  by read-back. If the Project cannot be confirmed, the Issue stays durable,
  `create` fails naming it, and a rerun with the same title and body continues
  that Issue instead of creating another. `project:*` labels are routing
  metadata, never proof of membership.
- **Quick execution**: a small, clear, bounded change may use normal task
  execution without a Requirement, Backlog Issue, or ceremonial OpenSpec
  change. This includes a regression repair that restores behavior
  unambiguously established by an accepted spec or equivalent durable contract.
- **Fresh non-trivial execution**: unless the user explicitly requests a
  technical managed task/OpenSpec change, create or reuse a Business
  Requirement, start its pre-authoring flow, produce the internal managed
  OpenSpec change(s) from handoff, link them back to the Requirement, start
  those managed tasks, and only then implement.
- **Existing Business Requirement**: start the supplied Requirement through
  `requirement_intake.py start` and resume its pre-authoring state.
- **Direct technical managed/OpenSpec path**: preserve the existing managed
  authoring/start path when the user explicitly supplies an existing managed
  Issue/OpenSpec task or explicitly asks to create a technical managed task.
  This path is an exception chosen by explicit technical intent; it is not the
  default meaning of `зафиксируй`.

User wording is evidence of the current intent, not a magic keyword. Direct
execution does not require a second `зафиксируй` instruction. A fixation-only
request always stops after the Requirement is durable unless the same request
also clearly authorizes execution.

## Requirement-first cross-surface contract

A Business Requirement is the normal human-facing unit of accepted non-trivial
work. It is an ordinary Development Backlog Issue labeled `type:requirement`
with business-language sections:

- `## Outcome`;
- optional `## Context`;
- optional `## Acceptance evidence`;
- `## Target repository`;
- optional `## Exclusions`;
- the machine-readable requirement-children block owned by
  `requirement_intake.py`.

Requirement fixation contains no `proposal.md`, `design.md`, `tasks.md`,
OpenSpec delta, file-level plan, or technical decomposition. The stable
pre-authoring identity is `requirement-<issue-number>`.

The semantics are identical across agent surfaces:

- A repository-local Codex, Claude Code, or other agent with a checkout MUST
  use `python3 scripts/requirement_intake.py create ...` for fixation.
- A ChatGPT Project with connected GitHub mutation access but no checkout uses
  the bounded adapter in [chatgpt-project-protocol.md](chatgpt-project-protocol.md)
  to create and read back the **same Requirement representation**. That adapter
  is a transport equivalent of `requirement_intake.py create`; it must not
  substitute a managed OpenSpec package merely because it lacks local shell
  access.
- Fixation is complete only when Project membership is confirmed. A connected
  adapter that cannot write the user-owned Project reports the Issue as
  durable but fixation **unconfirmed**; the operator-side
  `python3 scripts/requirement_intake.py reconcile-board --all` (or
  `--requirement owner/repo#N`) adds missing items idempotently and confirms
  them. This is never a user step. `start` and `advance` also ensure the card
  before claiming it.
- A fixation-only request stops as soon as the Requirement is durably created
  or the exact existing Requirement is reused.

When the user asks to execute a Business Requirement, the ordered flow is:

The target checkout must first prove its managed lifecycle: valid Backlog
routing, enabled OpenSpec/Git capabilities, required Requirement and managed
task entrypoints, and protected PR publication. Fixation and execution fail
early with missing evidence and a supported route when this cannot be proved.
An operator-managed downstream repository keeps its existing explicit opt-in;
operator routing parameters alone do not prove lifecycle support. Terminal
reconciliation checks the target again before marking the parent Done.

1. Run `python3 scripts/requirement_intake.py start --requirement owner/repo#N`.
2. Drive `scripts/orchestrate_pre_authoring.py --id requirement-N status`
   resumably. Record an explainable `select-depth` decision bound to the
   complete Requirement: `deterministic`, `bounded-evidence` (with explicit
   `--concern` scope), or `material-design`. An unchanged selection is reused;
   a changed Requirement invalidates it and its derived artifacts.
3. The deterministic path produces a direct handoff without snapshot or model
   work. Bounded evidence builds only selected projections through the routine
   read-only route and then produces a direct handoff. Neither path creates ADD
   or intents. For material design, build/reuse evidence, draft and approve ADD,
   pausing for a genuinely consequential open choice.
4. On the material path, decompose approved ADD elements into intents and
   prepare OpenSpec handoff envelopes.
5. For every ready handoff, author its managed bundle and run
   `python3 scripts/requirement_intake.py materialize-handoff --requirement owner/repo#N --handoff <ready-envelope.json> --bundle <authored-bundle-directory>`.
   The adapter validates current handoff readiness, creates or exactly reuses
   one managed Issue, repairs an interrupted parent/child link on retry, and
   reports success only after both link directions are confirmed. It does not
   invent proposal/design/spec content: the bundle remains the authored
   OpenSpec input. Each child carries `type:internal-change` and a parent
   back-reference.
   The back-reference is an exact standalone `Requirement: owner/repo#N`
   line. Authored prose such as `Parent Requirement:` does not replace it;
   materialization repairs and verifies the canonical line on retry.
6. Run `python3 scripts/execute_requirement.py advance --requirement owner/repo#N`
   from integration `main`. The source-owned supervisor reuses unique already
   linked children even if a historical handoff digest was refreshed, creates
   only missing children from authored bundles, and starts/resumes one child at
   a time in its isolated worktree with the exact predecessor receipt. It
   returns `implement-child` when the current agent must perform routed code
   work and verification in that worktree; rerun the same command after the
   child archive is committed. This is an internal agent continuation, not a
   user-facing stop or manual child list. With one child it uses ordinary managed publication and reconciles the parent after the exact child merge. With two or more ready children requiring joint delivery it composes and publishes a shared candidate through the protected path. Once the first child is verified and ready and two or more mandatory children are planned, `advance` opens one shared draft PR (never mergeable, queued or auto-merged) and appends each later ready child to the same branch and PR by fast-forward push; only when every mandatory child is present, the Requirement retrospective checkpoint exists and full checks pass on the exact final head is that PR marked ready and merged. Rerunning resumes the same PR.
   A verified clean ready child releases only its own active board writer
   claim; its worktree, Issue and receipt remain for shared publication.
   When a failed earlier attempt left this lifecycle's own ready receipt for
   an older head, `advance` supersedes it only when that receipt is valid,
   names the identical Requirement, child Issue, change and source branch, and
   its head is a strict ancestor of the new child head in the child worktree;
   the result lists it under `superseded_receipts`. A foreign, unreadable,
   divergent or same-head-different receipt stays a blocker.
   Potential same-project duplicates require an explicit reviewed
   `--confirm-distinct`; a material contract conflict still stops. OpenSpec
   becomes canonical only for each technical child after materialization.
   A changed predecessor, new edits to inherited files, or another task's claim
   remains a blocker. Historical linked children are reused by unique managed
   change identity even when a refreshed handoff has a different digest.

The Requirement's primary Project card is a projection of the same evidence.
`requirement_intake.py start` claims the card (`In progress`) as soon as pre-authoring state is durable, and `execute_requirement.py advance` repeats the idempotent claim at entry, so a Requirement under preparation never reads `Ready` to another agent. If the claim fails after the durable start the state is kept and the command is safe to rerun; the platform never writes `Ready` itself.
Started pre-authoring, ready handoff and child execution display `In progress`;
an unknown or blocked source displays `Blocked`. The richer read-through stage
and its reason remain available through `requirement_intake.py aggregate`.
Only terminal reconciliation after exact merged delivery of every mandatory child may set the parent card to `Done` and close its Issue. The single-child path uses ordinary managed publication; joint delivery uses a shared candidate for two or more children. Child `Done` statuses or ready receipts alone never complete the parent card. Retry terminal reconciliation with `python3 scripts/requirement_terminal.py reconcile --requirement owner/repo#N` for previously delivered parents.

Before final publication, run `python3 scripts/requirement_retrospective.py review-path --requirement owner/repo#N` and perform a bounded Requirement-level retrospective over its accepted intent, pre-authoring, handoff/decomposition, mandatory children and delivery path. Record only new meaningful process findings with the existing `agent_friction.py record --task owner/repo#N` mechanism; then run `python3 scripts/requirement_retrospective.py checkpoint --requirement owner/repo#N --result findings --event <id> --review-note "Reviewed actual Requirement path"` (repeat `--event` for multiple findings). If there are no new findings, use `--result none --review-note "Reviewed actual Requirement path"` after inspecting successful overrides, manual workarounds and state changes, known issue recurrences, and material drift observed in other owners' state. Repeat occurrences use the existing friction router. The receipt is machine-local, bound to the current parent body and linked child set, and required for terminal `Done`; rerun the review if it is absent or stale. Child post-task retrospectives remain separate. The parent checkpoint applies the same mandatory-signal rules as the task retrospective to events attributed to the Requirement (including legacy events recovered by branch or source issue): link each with `--event` or classify it with `--disposition <event-id>=resolved-in-task|already-recorded|expected-behavior` (a known-recurrence can only be linked), and name or `--accept-gap` an unreadable evidence source. Its `review-path` also prints the shared template and path-less project questions. The supervisor reports this command as the next action before publication when the checkpoint is missing.

Terminal single-child finish uses the ordinary exact worktree cleanup. A merged shared candidate records its exact worktree, branch and head for targeted cleanup; run the printed `scripts/worktree_cleanup.py cleanup` command from integration `main` after the publisher exits. The cleanup helper checks that the worktree is clean, inactive and still has the recorded identity.

At child start or resume, the managed adapter derives an ignored, disposable
`.claude/requirement-child-context/<change>.json` handoff from the exact imported
package, current repository head, linked Requirement identity, and (when used)
the ready predecessor receipt. The handoff points to the canonical OpenSpec;
it does not copy the Requirement's pre-authoring transcript or unrelated sibling
Issue bodies. A changed predecessor receipt or repository/package provenance
requires a fresh derivation before execution. The supervisor retains only the
Requirement identity, child lifecycle states, and consequential human decisions.

Requirement progress is read-through, never a second status ledger:
`python3 scripts/requirement_intake.py aggregate --requirement owner/repo#N`
retains its child-only `status` for compatibility and adds a `progress`
projection. `progress.stage` is one of `pre-authoring`, `design`,
`human-decision`, `ready`, `implementation`, `blocked`, `unknown`, or `done`;
before materialization it reads local orchestrator evidence; once children
exist it reads their authoritative Development Backlog Project statuses without
requiring machine-local pre-authoring state. Its `reason`, `diagnostics`, and
`sources` identify the evidence used. An unreadable, stale, unsupported, or
contradictory source fails closed to `unknown`; an explicit child block or
orchestrator escalation reports `blocked`. No output is persisted as a
Requirement field. The primary human-facing Project view should show
Requirements and exclude `type:internal-change`; child visibility remains
available through the parent links and dedicated/internal views.

## Incubator

`Incubator` is an optional pre-commitment planning layer backed by ordinary open
Issues in the configured Development Backlog repository. An incubated Issue
carries the dedicated `incubator` label but SHALL NOT carry a `project:*` label,
a priority label, Requirement label, managed authoring receipt, OpenSpec
package, routing decision, task workspace, or execution entitlement. It remains
outside both requirement-first intake and the technical managed lifecycle until
a human accepts it as work.

Keep an incubated item small and machine-editable. Record the target repository,
the idea or hypothesis, why it is worth remembering (including a source when
useful), and a **revisit condition**. Prefer an evidence/event trigger such as
“after enough routing executions exist” or “if this friction repeats” over an
arbitrary calendar date unless the decision is genuinely time-driven.

GitHub Project placement is a visualization layer, not the source of truth. A
Project may auto-add Issues matching `label:incubator` and expose a dedicated
`Incubator` view filtered by that label. Main Requirement views should exclude
`label:incubator` and `type:internal-change`. Do not add a `project:*` label
merely to make an incubated Issue appear in a Project.

Promotion requires explicit human acceptance of the idea as work. Create or
reuse the ordinary Business Requirement through the requirement-first fixation
path and leave fixation stopped there. After the Requirement identity exists,
close the incubated Issue with a link to the Requirement. Never promote an
incubated idea directly into OpenSpec or start implementation merely because it
was parked.

If the current agent surface cannot mutate GitHub Project views or fields, that
must not block durable incubation or Requirement authoring: create/update the
repository Issue and let configured Project automation/views surface it when
available.

## Evidence-first execution

Use repository evidence to narrow work before broad reading or unnecessary
human interruption. If the relevant file, symbol, owner, or contract is not
known, search first; then read only the likely evidence-bearing files needed to
make the next decision or act safely. If the canonical path is already known,
read it directly rather than performing a ceremonial search.

Resolve factual ambiguity from repository evidence when the repository can
answer it. Ask the user when a material product, intent, or scope choice remains
rather than turning a repository lookup into a question. Once enough evidence
exists to act safely inside the agreed scope, proceed instead of continuing
open-ended exploration by default.

## Commands

For fixation-only authoring from a repository checkout, prepare small text files
for the business sections and run:

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

To execute or resume an existing Requirement:

```bash
python3 scripts/requirement_intake.py start --requirement owner/repo#N
python3 scripts/orchestrate_pre_authoring.py --id requirement-N status
```

Follow the orchestrator's bounded next action until handoff is complete. Author
each resulting **internal** technical managed change through the existing
managed-task path, then link it immediately:

```bash
python3 scripts/managed_task.py create --bundle <directory>
python3 scripts/requirement_intake.py link-child \
  --requirement owner/repo#N \
  --child owner/repo#M
python3 scripts/start_managed_task.py owner/repo#M
```

The composed direct execution helper remains valid only for an explicitly
technical managed task:

```bash
python3 scripts/execute_managed_task.py --bundle <directory> --scope "<files/modules>"
```

For an already supplied managed Issue/OpenSpec task, continue to use:

```bash
python3 scripts/start_managed_task.py owner/repo#N
```

Candidate overlap and managed-package validation rules remain unchanged for
those internal/direct technical paths.

## Escalating quick work

Keep quick work quick. A directly requested small regression repair may remain
quick only when an accepted spec or equivalent durable contract unambiguously
establishes the expected behavior. Record that contract and proportionate
regression evidence. Where a reasonable test seam exists, demonstrate the
defect before repair, show the regression check passing after, and rerun the
original failure path. Where no reasonable automated seam exists, state the
limitation and actual alternative check truthfully; do not fabricate evidence.

If inspection reveals material behavioral,
architectural, compatibility, data-contract, cross-session, or scope impact —
or if a full active OpenSpec change is needed to govern the work — stop further
implementation and enter managed intake first. Do not create a normal active
OpenSpec change as a substitute for managed provenance.

The ordinary terminal lifecycle rejects an active OpenSpec change that lacks
managed provenance. This does not affect genuine quick work with no active
OpenSpec. Legacy/manual states need a reviewed recovery that records their real
source identity; never fabricate an Issue, delete work, or bypass the guard.

## Existing managed repositories

This document is platform-owned and arrives through normal release rollout.
Project-owned root `AGENTS.md` keeps local rules, but must include the stable
reference inserted by the rollout migration. The migration is additive and
marked; it does not replace project/domain or module-level instructions.

## Readable managed work identity

Requirement creation exposes `Work identity: BR-N`, derived from its Issue
number. Normal child linking, handoff materialization and import allocate and
read back `BR-N/Tn`, retaining the exact private `Requirement: owner/repo#N`
line. Ordinal reservations remain in the parent's existing Issue body when
checklist links are removed; child Issue claims support interrupted-write
recovery. Do not edit or delete those reservations when reordering the
checklist. Conflicting claims, duplicate ordinals and lost identity claims observable on
readback fail closed;
inspect both Issue records before retrying. GitHub body edits have no atomic
compare-and-swap: avoid concurrent manual prose edits while linking. A change
observed before replacement stops the operation, but an unseen edit overwritten
between that read and replacement cannot be detected. No separate registry is used.

Only validated BR tokens may supplement opaque public technical provenance.
This permission does not disclose the private Backlog name, URL, exact Issue
reference or Requirement prose. Native GitHub Assignee and project-owned area
and optional kind labels continue to own responsibility and taxonomy. Branch
and PR propagation is described in the next section.

## Readable managed publication identity

Through platform-owned start helpers, a linked managed child with validated canonical identity `BR-7/T2` starts on
`agent/br-7-t2-<change>`. Its change directory and worktree path still use the
change slug. Resume retains the registered branch, including legacy branches;
branch spelling never substitutes for canonical task provenance.

Child PR titles carry `[BR-7/T2]`. Shared Requirement PR titles carry `[BR-7]`
and the standard identity block lists every included child. Publication retries
repair the leading title prefix and the bounded `dev-platform:br-identity`
block while preserving the rest of an existing PR's title and body. The same
early shared draft PR grows by exact-head fast-forward publication. Shared
candidate refs, canonical manifest paths and opaque exact lineage retain their
ownership rules; readable manifest fields are additive presentation only.

Only validated BR tokens may cross the private/public boundary. Canonical
claims and committed provenance must agree before publication; parent prose,
private repository names, references and URLs are not presentation sources.
Unlinked tasks keep their existing branch and PR behavior. Project-owned
publication entrypoints remain owned by the project; shared orchestration passes
safe title/body arguments, and the portable `managed_work_identity.presentation`
helper supports adopting the same idempotent repair contract in a custom
publisher. Legacy custom start signatures remain callable for unlinked tasks
and recorded legacy branches. Creating a fresh linked branch stops before
creation until the owning helper accepts the optional `branch_name` keyword;
this prevents silently losing BR identity without changing worktree paths. Copier continues to preserve project-owned harness files and agent
instructions; this identity does not introduce product taxonomy.
