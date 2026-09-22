# Proposal: Give Architecture Health Review a cloud, scheduled execution surface

## Why

Architecture Health Review (`openspec/specs/architecture-health/spec.md`) is accepted as an advisory, read-only capability, but its spec defines only review content/scope; it has no execution environment, schedule, or trigger of its own today, and can only run inside an interactive local agent session. Requirement lehard/development-backlog#157 asks for a Platform Health Review that runs entirely in the cloud, on a schedule or by manual dispatch, without a running local computer. Architecture Health Review must gain this cloud/scheduled execution surface before it can be combined with the already cloud-capable Process Health Review.

## Current to target

Today: architecture-health-review is an opt-in, instruction-only capability invoked interactively by a local Claude Code / Codex session; no GitHub Actions workflow runs it.

Target: a new gh-aw GitHub Agentic Workflow runs the existing architecture-health-review instructions as a Codex job in GitHub Actions, on a schedule and/or `workflow_dispatch`, reusing the same read-only-tools / bounded-safe-outputs / cost-and-runtime-guardrail pattern already accepted for agentic-maintenance (`openspec/specs/agentic-maintenance/spec.md`). Findings remain advisory: the job may produce only a bounded declared safe output, and never edits code, opens a PR, or creates managed work.

## What changes

- Add a new gh-aw workflow (human-readable source `.md` plus its compiled/committed lock workflow) that runs Architecture Health Review's existing instructions as a read-only Codex job.
- Declare a bounded runtime and per-run AI-credit budget for the new job, following agentic-maintenance's guardrail pattern.
- Amend the architecture-health OpenSpec delta to accept a cloud/scheduled execution surface as part of the capability, while preserving its existing read-only/advisory/human-promotion requirements unchanged.
- Enable and validate this workflow centrally in `lehard/dev-platform` only (central-pilot-first, matching agentic-maintenance's existing rollout precedent); downstream managed-repository rollout stays a separate, later, explicitly approved change.

## Success evidence

- The new workflow can be triggered manually (`workflow_dispatch`) and, separately, on its configured schedule, in `lehard/dev-platform`, without any local computer running.
- A run produces only allow-listed safe outputs (no code edit, no PR, no managed-task creation) and stays within its declared runtime/AI-credit bounds.
- `openspec validate --strict` passes for the updated architecture-health delta, and existing architecture-health/agentic-maintenance behavior (local instruction-only invocation, human-promotion requirement) is unchanged.

## Constraints and non-goals

This change does not combine Architecture Health Review's trigger with Process Health Review's trigger (a separate linked change), does not define the combined durable report artifact (a separate linked change), and does not add any notification/delivery mechanism (a separate linked change). It does not change what Architecture Health Review evaluates or how it reasons about evidence. It does not roll the workflow out to any managed downstream repository.

## Delivery scope

A new `.github/workflows/*.md` (gh-aw source) plus its compiled lock workflow, and the architecture-health OpenSpec accepted-spec delta. No application/product code changes.
