## Why

OpenSpec 1.14.1+ (upstream issue Fission-AI/OpenSpec#1976, PR Fission-AI/OpenSpec#2020) reports a requirement whose description exceeds 500 characters as a warning, and `openspec validate --strict` fails on it. 37 of our 51 specs carry such requirements (229 in total), which blocks the upgrade from 1.13.2 to 1.15.0. The owner chose (2026-10-31) the upstream path: split the long requirements with the official procedure, in small portions, and bump OpenSpec only after `validate --all --strict` is green on 1.15.0. A repository-owned filter over `--strict` is rejected.

## What Changes

- Portion 1 of 3: in 18 specs, every requirement with a description over 500 characters is MODIFIED under its existing header with every scenario kept and its description cut to one behavior; each behavior removed from it is ADDED as its own requirement with its own scenario. Wording is reused verbatim; meaning does not change.
- Record the decision as `docs/decisions/0007-openspec-requirement-length.md` and index it.

## Capabilities

### Modified Capabilities

agent-runtime, agent-sessions, architecture-health, blocking-check-recovery, ci-safety, decision-layer-evaluation, decision-registry, engineering-capabilities, goal-definition, local-platform-hotfix, managed-rollout, managed-work-identity, model-routing, openspec-authoring, project-factory, public-distribution, shared-workspace, shared-workspace-coordination — form only.

## Impact

Specs and the decision registry only; no code, template or behavior change. The OpenSpec pin stays at 1.13.2 until portion 3.
