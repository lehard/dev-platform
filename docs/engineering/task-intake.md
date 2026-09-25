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
- **Quick execution**: a small, clear, bounded change may use normal task
  execution without a Requirement, Backlog Issue, or ceremonial OpenSpec
  change.
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
- A fixation-only request stops as soon as the Requirement is durably created
  or the exact existing Requirement is reused.

When the user asks to execute a Business Requirement, the ordered flow is:

1. Run `python3 scripts/requirement_intake.py start --requirement owner/repo#N`.
2. Drive `scripts/orchestrate_pre_authoring.py status` resumably. Record an
   explainable `select-depth` decision bound to the complete Requirement:
   `deterministic`, `bounded-evidence` (with explicit `--concern` scope), or
   `material-design`. An unchanged selection is reused; a changed Requirement
   invalidates it and its derived artifacts.
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
   user-facing stop or manual child list. With one child it uses ordinary managed publication and reconciles the parent after the exact child merge. With two or more ready children requiring joint delivery it composes and publishes a shared candidate through the protected path.
   A verified clean ready child releases only its own active board writer
   claim; its worktree, Issue and receipt remain for shared publication.
   Potential same-project duplicates require an explicit reviewed
   `--confirm-distinct`; a material contract conflict still stops. OpenSpec
   becomes canonical only for each technical child after materialization.
   A changed predecessor, new edits to inherited files, or another task's claim
   remains a blocker. Historical linked children are reused by unique managed
   change identity even when a refreshed handoff has a different digest.

The Requirement's primary Project card is a projection of the same evidence.
Started pre-authoring, ready handoff and child execution display `In progress`;
an unknown or blocked source displays `Blocked`. The richer read-through stage
and its reason remain available through `requirement_intake.py aggregate`.
Only terminal reconciliation after exact merged delivery of every mandatory child may set the parent card to `Done` and close its Issue. The single-child path uses ordinary managed publication; joint delivery uses a shared candidate for two or more children. Child `Done` statuses or ready receipts alone never complete the parent card. Retry terminal reconciliation with `python3 scripts/requirement_terminal.py reconcile --requirement owner/repo#N` for previously delivered parents.

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
python3 scripts/orchestrate_pre_authoring.py status --id requirement-N
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

Keep quick work quick. If inspection reveals material behavioral,
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
