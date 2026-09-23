# Proposal: Enable requirement-first intake for explicitly operator-managed downstream projects

## Why

Requirement-first intake is already the accepted operator-aware workflow, yet an ordinary downstream render cannot select that workflow without committing an operator TOML path. The three privately managed projects therefore retain the portable local OpenSpec guidance even though their operator installation supplies a shared external configuration.

## What changes

- Add one boolean, default-off Copier/operator-rollout selection that records only an explicit integration choice.
- Render and migrate the selected project's `[operator]` table to the stable `DEV_PLATFORM_OPERATOR_CONFIG` reference, reusing the existing resolver and preserving legacy explicit paths.
- Carry that choice from the private managed-project registry to the reviewed rollout; do not place target names or operator identity in public source.
- Use the same selection for Codex/Claude/task-intake guidance and retain ChatGPT's existing Requirement representation and direct technical exception.

## Success evidence

An explicitly selected downstream project renders and upgrades to requirement-first guidance and can resolve a supplied external TOML through `DEV_PLATFORM_OPERATOR_CONFIG`. A portable render ignores that environment and keeps its local OpenSpec flow. Registry validation and rollout matrix expose only the boolean needed by the workflow. The private registry selects planner-agent-lab, Jara_Fin, and cuby.

## Non-goals

This change does not publish operator configuration, invent a second resolver, alter backlog/project identities, auto-merge downstream rollout PRs, or make a portable project depend on an operator installation.
