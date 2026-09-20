# Interoperable agent handoff

Use this capability when live work must continue in **another context** — a fresh
Claude session, Codex or another agent, or a person taking over — and the current
context cannot simply be compacted in place. It produces one compact,
provider-neutral **navigation envelope** that points the receiver at canonical
state. It is not a task system, not a status ledger, and not a second source of
truth.

Do not produce a handoff for ordinary same-context continuation: if the work
stays in this session, a normal compact is sufficient and no durable artifact is
required. Do not use it to copy specs, diffs, or task lists around — those already
have canonical homes the envelope references instead.

## Boundary with provider routing handoff

The existing provider-local routing record (`.claude/model-routing/<change>.json`,
see [model routing](../../docs/engineering/model-routing.md)) already owns
**executor selection and delegated write containment** for a managed task:
supervisor/executor identity, tier/profile, and containment proof. This
capability does **not** duplicate or replace it and starts no executor. It covers
only the uncovered gap: carrying **cross-session, cross-provider, or
agent-to-human navigation context** so a different context can re-establish where
the work is. When a routing record exists, the envelope references it rather than
restating its fields.

## 1. What the envelope contains

Record only navigation context, in bounded form:

| Field | Content |
| --- | --- |
| Repository | `owner/repo` of the work. |
| Exact revision | The commit SHA the work is based on (`git rev-parse HEAD`). |
| Workspace | Branch and worktree/checkout path, when work is on a feature branch. |
| Managed task / OpenSpec | Development Backlog issue and `openspec/changes/<change>/`, when the work is managed. |
| Routing record | Path to the provider routing record, when one exists. |
| Canonical evidence | Links/paths to the authoritative artifacts the receiver must read (proposal/spec/design/tasks, verification receipt, relevant code and tests). |
| Verified facts | Statements the sender confirmed, each with the evidence that confirms it. |
| Unresolved assumptions | Statements the sender believes but did not confirm — explicitly not facts. |
| Blockers | What is currently preventing progress. |
| Next intent | The single next action the sender would take. |

Verified facts, unresolved assumptions, blockers, and next intent are kept
**separate**. An unsupported claim stays an assumption; it is never promoted to a
fact to make the envelope look more complete.

## 2. What the envelope must never contain

- secrets, tokens, or credentials;
- raw prompts or system instructions;
- chain-of-thought or private reasoning transcripts;
- large copied diffs or full spec/document bodies — reference the canonical
  source at its revision instead.

## 3. Receiving a handoff

The receiver treats the envelope as navigation, not authority:

1. **Validate identity and freshness first.** Compare the envelope's repository,
   exact revision, and managed task / OpenSpec identity against the current
   state. If the revision or task identity does not match — for example `HEAD`
   moved, the branch was rebased, or the managed task was superseded — the
   handoff is **stale**: re-read the canonical sources and treat the envelope's
   facts as unverified until re-confirmed.
2. **Re-establish context from canonical references**, not from the envelope's
   prose: open the managed OpenSpec, the routing record, and the cited evidence.
3. **Carry assumptions forward as assumptions.** Confirm or drop each one from
   canonical evidence before relying on it.
4. **Start no work on the strength of the handoff alone.** Receiving an envelope
   grants no execution authority and no write access; begin implementation only
   through the normal managed entrypoints once identity and freshness check out.

## 4. Authority boundary

Creating or receiving a handoff performs **no** branch, worktree, commit,
comment, GitHub, Development Backlog, Project, or OpenSpec state mutation, and
confers no permission to execute. It only records and reads navigation context.

## Representative shapes

- **Claude → Codex.** Claude has materialized a managed OpenSpec change and
  confirmed a failing reproducer. The envelope names the repo, `HEAD` SHA,
  branch/worktree, the backlog issue and change dir, the routing record, the
  reproducer command as a verified fact, "the fix belongs in module X" as an
  unresolved assumption, and "write the regression test" as next intent. Codex
  validates the SHA, opens the change, and continues.
- **Codex → Claude.** Codex is blocked on an ambiguous spec scenario. The
  envelope's blocker is that scenario; next intent is "get the scenario
  clarified before coding". Claude checks task identity, sees it still matches,
  and picks up the clarification.
- **Agent → human.** An agent hands off at end of session. The person reads the
  envelope, follows the canonical references, and sees that `HEAD` has since
  moved — so they re-read the current spec rather than trusting the stale fact
  list.

## Negative cases

- **Ordinary compact.** Work continues in the same session: no envelope.
- **Existing task state is enough.** The managed OpenSpec and routing record
  already carry everything the next context needs: reference them, do not restate
  them in a parallel document.
- **Unconfirmed assumption.** A belief without evidence is recorded under
  assumptions, never under verified facts.
- **Changed HEAD.** The revision no longer matches: the receiver treats the
  handoff as stale and re-reads canonical sources.
