# Design: Disposable experiment, durable decision

## Context

Some managed work carries material product, UI or technical uncertainty that an
observable experiment resolves faster than analysis. Dev Platform already has a
provider-neutral optional-capability lifecycle (#87); a prototype/spike mode is
one more capability on it, not a new subsystem.

## Decisions

1. **Reuse the capability lifecycle.** One canonical descriptor
   (`dev-platform/capabilities/bounded-prototype.toml`) plus a hash-pinned
   instruction file; opt-in through `dev-platform/capabilities.toml`; derived
   provider skill surfaces only when enabled. No prototype-specific registry,
   config, branch, issue, progress file or status.
2. **Trigger narrowly.** Only when a bounded experiment can materially reduce
   unresolved uncertainty that evidence cannot settle. A clear task, a mechanical
   change, or a bounded fix with an established approach gets no prototype step.
3. **Isolate the work.** Run in a temporary throwaway workspace or an explicitly
   project-declared prototype area. Never modify production source, dependencies,
   credentials or task state.
4. **Bound the experiment.** Declare the question, the options/hypotheses, and
   time/iteration/cost bounds up front. Stop when bounds are exhausted or
   evidence is insufficient, and record that outcome rather than pushing on.
5. **Record a decision, not a plan.** Capture question, options, bounds,
   observation, decision (or remaining uncertainty) and an evidence
   reference/path in bounded form — no transcript, secrets or sensitive payloads.
6. **No automatic promotion.** Prototype code is disposable by default and cannot
   become production source automatically. Follow-on implementation enters the
   ordinary managed OpenSpec lifecycle and is written fresh against the contract.
7. **Clean by default.** Temporary state is removed when the experiment
   concludes; retention is explicit, bounded and policy-compatible, and retained
   artifacts are still not production source.
8. **Safety rules stay authoritative.** Repository, credential, network, data and
   prohibited-authority rules are not relaxed for an experiment; a request that
   needs any of them is refused with the boundary reported.

## Spec placement

The capability's observable behavior is added to the existing
`engineering-capabilities` spec as additive requirements, consistent with how
`selective-domain-interrogation` and `systematic-bug-diagnosis` extended
`agent-workflow` rather than each spawning a near-empty spec. The requirements
are scoped to the `bounded-prototype` capability by name.

## Provider neutrality

The descriptor and instruction are provider-neutral. Claude and Codex skill
surfaces are derived; no provider command path, nested CLI, or second router is
introduced. The eval decision is delegated to the shared `capability_evals.py`
core with a bounded deterministic fixture (ten positive, ten hard-negative
prompts, three samples each).

## Bounded-adaptation provenance

No upstream "prototype/spike" skill is vendored or fetched. If a specific
external pattern is adapted during implementation, it is pinned by exact revision,
path, license and content hash in `docs/engineering/engineering-capabilities.md`,
matching the review table format already used for the other capabilities. If
nothing external is adapted, that is recorded explicitly.

## Risks

Low risk: instruction-only, opt-in, no runtime dependency, no production write
authority. The main hazard the design guards against is an experiment quietly
becoming production code or touching production state; decisions 3, 5, 6 and 8
plus the prohibited-authority scenario are the mitigations, exercised by the
eval fixture's negative controls.
