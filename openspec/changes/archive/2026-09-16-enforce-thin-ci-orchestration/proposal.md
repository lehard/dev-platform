# Proposal: Keep CI providers thin and repository execution portable

## Why

Dev Platform already keeps most downstream verification logic in repository-owned entrypoints such as `platform_doctor.py`, `openspec_lifecycle.py` and `select_checks.py`, while GitHub Actions supplies events, environment bootstrap and status integration. That boundary is useful but not explicit enough to prevent future coding agents from putting new portable test/build/release/deploy logic directly into provider-specific workflow YAML.

The goal is to make the existing direction durable without replacing GitHub Actions, introducing a generic CI abstraction, or refactoring working workflows for aesthetic reasons.

## What Changes

- Add an explicit thin-CI invariant: portable execution logic belongs in repository-owned commands/scripts; CI-provider configuration orchestrates those entrypoints.
- Expose the invariant through bounded agent-facing instructions so new agent-authored CI/CD work starts from the repository execution surface rather than provider YAML.
- Verify the generated downstream workflow against that invariant and repair only concrete violations.
- Keep GitHub-native concerns such as triggers, permissions, concurrency, checkout/bootstrap, secrets wiring and check/status integration in GitHub Actions.
- Preserve GitHub Actions as the current default control plane and leave self-hosted/alternate providers as future execution choices, not present-day abstractions.
