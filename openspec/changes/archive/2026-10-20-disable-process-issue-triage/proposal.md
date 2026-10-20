## Why

`Process Issue Triage` (gh-aw, `.github/workflows/process-issue-triage.md` + generated `.lock.yml`) runs on every `process` label and exhausts its daily AI-credit budget; the gh-aw failure reporting of those runs produced 28 issues and hundreds of comments with no value (Process Health Review of 2026-10-11). On 2026-10-19 the owner decided to disable automatic triage; a scheduled batch triage was rejected. Friction review already happens in the periodic Process Health Review.

## What Changes

- Remove `.github/workflows/process-issue-triage.md` and its compiled `.github/workflows/process-issue-triage.lock.yml`. With no workflow file on the default branch, no `issues` event or manual dispatch can start triage, and gh-aw can no longer emit its budget/failure issues or comments for it.
- `scripts/validate_agentic_workflows.py` and `scripts/cloud_maintenance_preflight.py` stop listing the triage workflow.
- Tests stop asserting triage source/lock properties and instead assert that the triage workflow is absent.
- `docs/agentic-workflows.md`, `docs/engineering/agent-workflow.md` and the template `agent-workflow.md.jinja` state that event-driven triage is disabled by owner decision and that friction is reviewed by the Process Health Review.
- `agentic-maintenance` spec: the triage-pattern requirement is removed, the read-only safe-output requirement is restated for every installed cloud maintenance workflow instead of triage, and a requirement records that event-driven process triage is not installed.

## Capabilities

### Modified Capabilities

- `agentic-maintenance`: event-driven process-issue triage is no longer part of the cloud maintenance layer.

## Impact

`.github/workflows/process-issue-triage.{md,lock.yml}` (deleted), `scripts/validate_agentic_workflows.py`, `scripts/cloud_maintenance_preflight.py`, `tests/test_agentic_workflows.py`, `tests/test_ci_guardrails.py`, `tests/test_cloud_maintenance_preflight.py`, `docs/agentic-workflows.md`, `docs/engineering/agent-workflow.md`, `template/docs/engineering/agent-workflow.md.jinja`, platform manifest. No downstream workflow change: triage was never rolled out to managed projects.

## Non-goals

Closing, deleting or editing already created triage service issues and comments; a scheduled or batch triage replacement; changes to the weekly process review, architecture health review or friction routing.
