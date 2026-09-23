# Design: Generic operator-integration selection

## Decision

`operator_integration` is a boolean Copier answer and optional private-registry field. Its default is `false`. A `true` value is intentionally generic: it causes the project to record `[operator] enabled = true` and `config_env = "DEV_PLATFORM_OPERATOR_CONFIG"`, never a path or any installation identity.

The already accepted resolver remains the only resolution mechanism: explicit project opt-in gates environment lookup, and the external TOML provides backlog and rollout state. Existing projects that supplied `operator_config_path` keep their path-based rendering as a compatibility input.

## Propagation and migration

The private registry validates the optional boolean and emits it in the Actions matrix. `rollout_project.py` receives that matrix value, sets the machine-owned Copier answer on the rollout branch before its guarded update, and candidate bootstrap writes the generic table only if no `[operator]` table already exists. A conflicting existing table is a fail-closed reviewed-project condition; a pre-existing enabled table is preserved. The guarded configuration comparison allows only this deterministic platform-owned activation.

The selector is deliberately not an implicit environment feature flag. An unselected project remains portable even when `DEV_PLATFORM_OPERATOR_CONFIG` is present.

## Guidance

Every rendered condition that currently recognizes a legacy `operator_config_path` recognizes the boolean selection as well. Operator-integrated Codex/Claude guidance describes Requirement fixation, fresh execution, existing Requirement start, explicit direct technical managed work, and quick-task preservation. The ChatGPT Project protocol continues to create/read back the same Requirement and follows the same child-linking model.

## Verification

Unit and template contract tests cover registry validation/matrix, CLI argument propagation, safe bootstrap transitions, legacy compatibility, portable rendering, enabled rendering, resolver gating, and the five intake paths. A controlled local exact-version Copier update validates the migration. GitHub Project inspection verifies the primary view filters `type:internal-change`; if API capabilities do not safely mutate the view, the verification receipt supplies a single exact manual UI step.
