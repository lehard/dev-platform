# Proposal: Add interoperable agent handoff

## Why

Live work moves between Claude, Codex, other agents, and people. Today the only
cross-context carriers are an ordinary compact (same context only) and the
provider routing record (executor selection and write containment for one
managed task). Nothing gives a *different* session, provider, or a human a
compact, safe way to re-establish where in-progress work stands without copying
canonical documents around or letting a summary become a competing source of
truth.

## What Changes

- Consume the shared optional engineering capability lifecycle (Development
  Backlog #87) for identity, provenance, opt-in, provider materialization, and
  update/removal — no handoff-specific registry, config, or update path.
- Add one provider-neutral navigation envelope for continuation in another
  agent, provider, or human context. It references repository, exact revision,
  branch/worktree, managed task/OpenSpec, the provider routing record when one
  exists, and canonical evidence.
- Keep verified facts separate from unresolved assumptions, blockers, and next
  intent; an unsupported claim stays an assumption.
- Require the receiver to validate repository, revision, and managed-task
  identity first and treat a mismatch as stale, re-reading canonical sources.
- Compose with the existing provider routing handoff instead of duplicating it;
  add no orchestrator and start no executor.
- Carry no secrets, raw prompts, chain-of-thought, or large diff/spec copies,
  and perform no GitHub/Backlog/Project/OpenSpec/worktree mutation.

## Outcome and success criteria

Qualitative instruction/workflow change; success is directly observable, not a
KPI:

- One provider-neutral handoff schema/instruction exists and is materialized
  only through the #87 lifecycle.
- A receiver can reconstruct current context from the canonical references and
  can see stale or missing references.
- The instruction and deterministic fixture cover Claude → Codex, Codex →
  Claude, and agent → human continuation.
- Negative cases are covered: ordinary same-context compact, "existing task
  state is enough", an unconfirmed assumption, and a changed `HEAD`.
- Creating or receiving a handoff changes no GitHub/OpenSpec/Project state and
  grants no execution authority.
- No handoff-specific registry/config/update lifecycle is introduced.

## Non-goals

Automatically launching another agent, a new orchestrator or dispatcher, copying
full specs/diffs, and long-term agent memory are out of scope.
