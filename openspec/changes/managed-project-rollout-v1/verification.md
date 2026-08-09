# Semantic verification: managed-project-rollout-v1

OpenSpec-Verify: PASS
Verification-Method: equivalent-review-chatgpt-github

## Scope

Reviewed the active proposal, delta spec, design, task plan and PR #11 implementation across OpenSpec's semantic dimensions: completeness, correctness and coherence.

## Completeness

PASS.

- Central inventory covers all 13 downstream repositories visible/considered in this rollout pass: 1 `managed`, 9 `candidate`, 3 intentionally `excluded`.
- Only `managed` entries can enter the Actions rollout matrix; direct manual targeting of non-managed states is rejected.
- Immutable release publication dispatches the rollout workflow with the exact released tag.
- Rollout validates that a requested target is an actually published immutable GitHub Release before downstream credentials/mutation.
- Private template source access and downstream writes are handled through a dedicated GitHub App with separately down-scoped short-lived tokens.
- Exact-version Copier update, conflict/reject detection, doctor/project checks, deterministic branch creation, push and PR creation are implemented.
- No auto-merge path is present.
- First-time adoption remains separate from recurring rollout.
- Stale adoption documentation about private cross-repository reusable CI was removed and replaced with the current self-contained CI model.
- One-time GitHub App setup and retry/failure handling are documented.
- Central CI validates registry/tooling/tests and preserves the existing three-profile Copier upgrade smoke.

## Correctness

PASS after findings were resolved.

Material findings found during review and fixed before this PASS:

1. **Private source credential scope** — the initial design created an App token scoped only to the target repository, which could not fetch the private `lehard/dev-platform` Copier source. Fixed by creating a read-only source token scoped only to `dev-platform` and a separate target write token.
2. **Workflow-file write permission** — the initial target token requested Contents/Pull-request write only, but Dev Platform can update `.github/workflows/*`. Fixed by requiring/down-scoping `Workflows: write` on the target token.
3. **Registry completeness** — the initial registry represented only a subset of known repositories, leaving omission as an implicit state. Fixed by classifying all 13 downstream repositories as `managed`, `candidate`, or intentionally `excluded`, with exclusion reasons enforced.

Additional correctness checks:

- Copier `gh:` source syntax resolves to HTTPS GitHub URLs, matching the process-only Git URL credential rewrite used by the rollout helper.
- Stable SemVer parsing rejects mutable/non-release refs and downgrade attempts.
- Existing open same-version rollout PRs are treated as already pending; existing unexpected branch collisions fail closed.
- Rollout branches are pushed without force and default branches are never directly mutated by central automation.
- GitHub-owned Actions references introduced by this change are SHA-pinned.

## Coherence

PASS.

- `AGENTS.md`, README, adoption guide, release policy and managed-rollout documentation agree on the same lifecycle and registry states.
- OpenSpec design/spec were updated before implementation whenever semantic review changed the credential/permission/registry model; there is no known silent divergence.
- Central release policy remains consistent with immutable SemVer releases and reviewed Copier PR boundaries.
- Candidate/excluded repositories remain non-mutating, while the one currently Copier-managed pilot (`lehard/planner-agent-lab`) is the sole automatic rollout target.

## Automated evidence

Platform CI run #74 on the final implementation state completed successfully across `light`, `standard` and `multi-agent`, including:

- shared script compilation;
- managed-project registry validation;
- unit/workflow contract tests;
- OpenSpec lifecycle hygiene;
- strict OpenSpec validation;
- exact Copier 9.17.0 install;
- fresh template render/doctor;
- Copier upgrade smoke.

## Operational boundary

The GitHub App itself and repository variable/secret are an external one-time operator setup and are intentionally not fabricated by repository code. Until they exist, a live rollout job is expected to fail at the explicit App-configuration preflight without mutating any downstream repository. The first `v1.2.0` release will exercise that fail-closed boundary; after the App is configured, the same workflow can be manually retried for the exact release.
