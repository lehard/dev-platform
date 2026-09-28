## Placement

`agent-runtime` stays scoped to execution backends such as DeepSeek Harness and Ouroboros. A new `upstream-substitution` spec owns evaluation of non-runtime agent infrastructure. It reuses the three-state decision vocabulary (`adopt-next-step`, `watch-only`, `reject-for-now`) so reports and reviewers use one language. The unit of decision is one *overlapping capability* rather than a whole tool, because a large upstream may be worth adopting for one area and rejected for another.

## Pilot model

- **Candidate:** the exact latest stable release. Prereleases may be read as roadmap evidence but never become the evaluated default.
- **Sandbox:** isolated HOME and tool-install prefix, local disposable repositories, no real credentials, no writes to shared operator configuration, to other agents' worktrees, or to real managed projects. Upstream self-update, shell-profile injection, auto-applied hooks/MCP and usage reporting are disabled unless a scenario measures them inside the sandbox.
- **Scenarios:** at least one representative Dev Platform workflow, plus at least one managed-project scenario rendered freshly from the current template with the agent surfaces in use (Claude Code and Codex today).
- **Judgement:** Dev Platform acceptance judges the result, not upstream self-reports.

## Decision record

The record is one durable document per upstream evaluation. For each capability it holds the decision and these evidence fields:

- exact version, scenarios and observed behavior (not only desk research);
- lifecycle coupling, migration cost, and release cadence and churn;
- security/privacy (what leaves the machine, arbitrary-command surfaces);
- failure and rollback behavior, and Codex/Claude compatibility;
- the ownership classification: direct, thin adapter, or Dev Platform-owned;
- the maintenance-surface baseline (source, tests and docs lines at the evaluated revision), plus the retirement set or the evidence for retention.

A retention whose only reason is that "an own implementation exists" fails review.

## Adoption

An `adopt-next-step` only authorizes a separately authored managed change. That change must:

- integrate as an opt-in capability or thin adapter with an exact version and exact reviewed resource-revision pin;
- disable or prove containment of self-update and mutable pulls;
- ship through the immutable release and controlled rollout, with rollback to the prior release;
- retire the superseded own implementation, or record a bounded transitional exit criterion;
- re-verify the lifecycle core.

## Non-transferable core

A substitution decision may not transfer requirement-first/OpenSpec lifecycle, task identity, writer/worktree containment, verification/publication, or release/rollout ownership. Proposing that transfer needs its own evidence-based change, which this capability does not authorize.

## Verification

Semantic OpenSpec verification checks the spec against this design. Full validation runs because `AGENTS.md` is an instruction-behavior surface, and the doc link check covers the new pointer.
