# OpenSpec workflow

OpenSpec is the planning contract for non-trivial product and architecture changes. It complements repository process rules and project-specific verification.

## Contract model

Do not model these as a flat precedence ladder:

1. `AGENTS.md` constrains **how work may be performed**.
2. `openspec/specs/` states the **accepted current behavior**.
3. `openspec/changes/<active>/` states the **approved delta** currently changing that behavior.
4. Code implements current behavior plus approved active deltas.

The target behavior during an active change is therefore `current specs + active delta`, subject to process/safety constraints.

## No silent divergence

If implementation reveals that the plan must change, update the relevant artifact before proceeding in a different direction:

- intent/scope -> `proposal.md`;
- observable behavior -> delta specs;
- technical approach -> `design.md`;
- execution order/dependencies -> `tasks.md`.

Do not knowingly make code and OpenSpec disagree and plan to repair the docs later.

## Verify before archive

For non-trivial changes:

`plan review -> implementation -> project tests/QA -> /opsx:verify -> archive`

`/opsx:verify` is semantic implementation review; `openspec validate` is structural validation. Neither replaces project-specific tests, E2E, browser/render QA, migrations or operational checks.

The expanded OpenSpec verify workflow must be enabled for the repository before a non-trivial change is archived. If it is absent, run `openspec config profile` to enable `verify`, then `openspec update` to regenerate tool integrations.

## OpenSpec version policy

`.dev-platform.toml` records the platform-tested OpenSpec version and minimum compatible version. `platform_doctor.py` warns when the local CLI is newer than the tested version and fails when it is below the minimum. The platform does not silently upgrade a user's global CLI.
