# Proposal: Materialize selected capability surfaces before platform_doctor.py in generated CI

## Why

A real `Roll Out Platform` dispatch for `lehard/Jara_Fin` failed with a Copier `.rej` conflict on `.github/workflows/dev-platform.yml`, because Jara_Fin had locally patched a generic platform gap: `platform_doctor.py`'s capability audit fails whenever a project has any capability enabled in `dev-platform/capabilities.toml`, because the derived provider surfaces it checks for (`.claude/skills/dev-platform-*/SKILL.md`, `.codex/skills/dev-platform-*/SKILL.md`) are deliberately gitignored and therefore absent on any fresh checkout — including every GitHub Actions CI run. The generated CI never ran `capability_manager.py sync` to materialize them first. This was previously masked because `dev-platform`'s own selection is empty, `lehard/cuby`'s is empty, and `lehard/planner-agent-lab` has its derived surfaces anomalously committed (against the platform's own gitignore contract).

## What Changes

- `template/.github/workflows/dev-platform.yml.jinja`: add a "Materialize selected capability surfaces" step (`python3 scripts/capability_manager.py sync`) immediately before "Validate platform contract" (`platform_doctor.py`).
- `tests/test_capability_manager.py`: new regression reproducing the fresh-checkout failure (`audit()` reports `status: error` with enabled capabilities and no prior `sync()`) and its fix (`sync()` then `audit()` reports `status: ok`).
- `tests/test_template_contract.py`: new regressions asserting the generated CI step ordering (sync before doctor) and that the derived surface gitignore patterns remain present.

## Success Evidence

A real `copier copy` render with capabilities enabled reproduces `platform_doctor.py` exit 1 before the fix and exit 0 after, running exactly the new CI step's commands. The materialized surfaces remain untracked (`git check-ignore` matches both provider patterns). A full-tree diff against the unfixed render shows exactly one new step added to exactly one file.

## Dependencies

None directly, but this is discovered as part of restoring real end-to-end managed rollout for `lehard/Jara_Fin` (which has capabilities enabled and correctly does not commit derived surfaces), continuing the same investigation as `add-legacy-baseline-bridge`, `fix-rollout-trailing-blank-lines`, `fix-reconcile-missing-registry-flag`, and `fix-dev-platform-yml-trailing-blank-line`.
