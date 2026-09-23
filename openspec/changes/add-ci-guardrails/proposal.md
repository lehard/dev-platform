# Proposal: Add CI guardrails

## Why

The existing Python test suite missed an undefined name. Several GitHub Actions jobs rely on implicit token permissions or the platform maximum runtime.

## What changes

- Add a lightweight, locally runnable Python static gate for high-signal defects and run it in central platform CI.
- Declare explicit least-privilege GitHub token permissions for central and generated platform-owned workflows and bounded job timeouts for long-running jobs.
- Add focused regression checks for the lint configuration and workflow guardrails.

## Success evidence

A deliberately undefined Python name fails the local gate; current source passes without broad style changes; workflow validation confirms explicit permissions and deadlines; required platform checks pass.

## Constraints

No mandatory mypy migration, mass formatting, or change to project-owned application CI. Preserve permissions needed for release and rollout side effects.
