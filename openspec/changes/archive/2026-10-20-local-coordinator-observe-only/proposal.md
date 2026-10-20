## Why

The owner decided (2026-10-10, DEC-0003 draft) that only the CI coordinator (`publication-queue` workflow, GitHub App `dev-platform-bot-lehard`) publishes to `main`. Today the local coordinator mode runs the same integrate-and-merge worker with the owner's `gh auth` identity, so locally developer and integrator are one identity, and `docs/engineering/agent-workflow.md` still suggests a local worker retry. The local preflight also demands repository push permission, which only matters for a local integrator.

A side blocker from the same day: `execute_requirement.py advance` stopped locally with `harness GitHub push requires coordinator GH_TOKEN`. The harness push to a candidate (or Requirement integration) branch needs ordinary write access, not coordinator authority, but `harness_push_env` accepts only an exported `GH_TOKEN`.

## What Changes

- `publication_queue.py worker --mode local` performs no candidate work: it exits non-zero with a diagnostic naming the CI coordinator as the only integrator and pointing to `publication_queue.py status` and `publication_queue.py preflight --mode local`. It does not mint or require an App token.
- `preflight --mode local` drops the `repository-permission` push probe; the remaining local checks (tools, `gh` authentication, coordinator App identity, trust configuration, enabled coordinator, repository identity, pull-request read) stay and keep their fail-explicit behaviour.
- `lifecycle_workers.harness_push_env` obtains the push credential from `gh auth token` (gh's own precedence: an exported `GH_TOKEN` — the App installation token in CI — else the operator's `gh` login) and fails explicitly when `gh` reports no credential. The token still lives only in the one push process environment, never in argv, config files or writer checkouts, and never in diagnostics.
- The publication-queue spec states that the local mode is observe-only; the lifecycle-workers spec states the candidate push credential source.
- `docs/engineering/agent-workflow.md` and other coordinator docs drop the local worker retry advice.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `publication-queue`: local coordinator mode is observe-only; local preflight does not prove push permission.
- `lifecycle-workers`: harness candidate-branch push credential comes from the active `gh` credential.

## Impact

`template/scripts/publication_queue.py`, `template/scripts/lifecycle_workers.py`, `docs/engineering/agent-workflow.md` (and any coordinator doc that recommends a local worker run), tests and the regenerated platform manifest. The GitHub ruleset on `main` is applied afterwards as an operator step of the parent Requirement. Downstream projects are not changed by this Requirement beyond the normal release of the template scripts.

## Non-goals

Issuing App tokens on the local machine; moving the CI-only merge boundary into downstream projects; sandboxing the Claude writer; removing detection-only containment logic.
