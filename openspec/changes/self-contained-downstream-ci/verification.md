# Verification: self-contained downstream CI

## Result

Semantic implementation review: **PASS**.

## Completeness

- Generated downstream CI no longer calls a private cross-repository reusable workflow.
- The generated job still runs platform-owned `scripts/select_checks.py`.
- `actions/checkout` and `actions/setup-python` are pinned to full immutable SHAs.
- `platform_ci_ref` remains in schema v2 for backward compatibility.
- Version is advanced to `1.0.1` for an explicit patch release.

## Correctness

- Fresh Copier render passes for `light`, `standard`, and `multi-agent`.
- Upgrade smoke from stable `v1.0.0` passes for all three profiles after escaping the GitHub `${{ ... }}` expression from Jinja rendering.
- The new workflow has no dependency on repository-level private Actions Access, which directly addresses the Planner Agent Lab dogfood failure mode (`jobs=0`, `referenced_workflows=[]`).
- Project-specific quality pipelines remain independent; this change only alters the generic platform check layer.

## Coherence

The change strengthens the existing reviewed-update model rather than weakening it: workflow logic is now copied and versioned in the downstream repository and changes only through reviewed Copier updates. There is no mutable remote execution channel.

## CI evidence

Platform CI run #20 passed on `61aafa750fd6377a0fe9b39e568f7df79e150361`, including unit tests, fresh renders and Copier upgrade smoke for all configured profiles.

## OpenSpec verify note

This is the recorded completeness/correctness/coherence review expected from the platform verify policy. The GitHub connector cannot literally invoke the local `/opsx:verify` slash command, so this file does not claim that command itself ran.
