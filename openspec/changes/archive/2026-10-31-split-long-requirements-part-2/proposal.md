## Why

OpenSpec 1.14.1+ fails `openspec validate --strict` on a requirement description over 500 characters (Fission-AI/OpenSpec#1976, #2020). DEC-0007 (`docs/decisions/0007-openspec-requirement-length.md`) records the owner's choice: split the long requirements with the upstream procedure, in portions, then bump OpenSpec. Portion 1 covered 18 specs; 174 long requirements remain in 19 specs.

## What Changes

- BR-799 portion 2 of 3 (part A): in 9 specs, every requirement with a description over 500 characters is MODIFIED under its existing header with every scenario kept and its description cut to one behavior; each behavior removed from it is ADDED as its own requirement with its own scenario. Wording is reused verbatim; meaning does not change.

## Capabilities

### Modified Capabilities

agent-instructions, agent-workflow, managed-task-intake, platform-ci, platform-config, platform-explorer, platform-health-review, requirement-metrics, upstream-substitution — form only.

## Impact

Specs only; no code, template or behavior change. The OpenSpec pin stays at 1.13.2 until portion 3.
