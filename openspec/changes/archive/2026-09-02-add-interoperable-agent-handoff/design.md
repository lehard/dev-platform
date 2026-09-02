# Design: Ephemeral navigation envelope

## Decisions

1. **Capability mechanics come from #87.** This change owns handoff behavior
   only; shared identity/provenance/opt-in/materialization/update/remove stay in
   the optional-capability foundation. No handoff-specific registry or config.
2. **Navigation, never source of truth.** The envelope points at canonical
   state; it does not restate specs, task lists, or status, and it is not a
   task/spec/status system.
3. **Bounded envelope fields.** Repository, exact revision, workspace
   (branch/worktree), managed task/OpenSpec, routing record, canonical evidence,
   verified facts (each with its evidence), unresolved assumptions, blockers,
   next intent.
4. **Facts and assumptions are separated.** An unsupported claim stays an
   assumption and is never promoted to a fact.
5. **Freshness is the receiver's first check.** Repository, revision, and
   managed-task identity are compared before anything else; a mismatch (moved
   `HEAD`, rebase, superseded task) makes the handoff stale and forces a re-read
   of canonical sources.
6. **Composes with provider routing, does not duplicate it.** The routing record
   (`.claude/model-routing/<change>.json`) owns executor selection and delegated
   write containment. The envelope references it and covers only the uncovered
   cross-session/cross-provider/agent-to-human navigation gap. No second
   dispatcher, no orchestrator, no executor launch.
7. **No authority.** Creating or receiving a handoff performs no
   GitHub/Backlog/Project/OpenSpec/worktree mutation and confers no permission to
   execute; work still begins only through the normal managed entrypoints.
8. **Exclusions.** No secrets, raw prompts, chain-of-thought, or large copied
   diffs/specs. Same-context compaction requires no handoff artifact.

## Boundary sketch (current → target)

- Current: same-context compact, or a routing record scoped to one managed
  task's executor/containment. A person or fresh/other-provider context resuming
  work has no compact, safe carrier.
- Target: an opt-in instruction that produces/consumes one navigation envelope
  for exactly that gap, with freshness validation and no authority.

## Risks and mitigations

- **Risk: the envelope is treated as authoritative and drifts from canonical
  state.** Mitigation: the instruction forbids restating canonical content,
  requires reference-by-revision, and makes staleness detection the receiver's
  first step.
- **Risk: duplicating the routing handoff.** Mitigation: explicit boundary in
  the instruction and design; the envelope references the routing record rather
  than re-declaring executor/containment fields.
