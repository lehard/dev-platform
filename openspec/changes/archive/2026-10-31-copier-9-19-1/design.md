## Context

The accepted platform-config requirement "Platform tests one explicit, current-stable Copier version" lists the copies that must agree and asks for confirmation against the primary upstream source. `tests/test_template_contract.py` asserts the agreement.

## Decisions

- **Exact pin 9.19.1** everywhere the platform records the tested version; `_min_copier_version` follows it so an update to this release runs with the fixed Git handling.
- **Evidence with an isolated install.** Copier 9.19.1 runs from a session-local virtualenv on PATH; the machine-wide Copier is not changed. Checked: a v3.0.0 render updated to the change head (with a project-owned edit and the managed bootstrap), a fresh render, the repository's Copier smoke tests (`tests/rollout_recopy_smoke.py`, `tests/project_harness_adoption_smoke.py`) and rollback (Copier 9.18.2 re-running the same update reference on a project updated by 9.19.1).
- **#528 overlap.** Local hotfix preservation stays with #528; nothing here changes the hotfix or recopy logic.
- **Existing fallback reported, not extended.** `platform_doctor.py` keeps its documented default for a project without `[tools.copier]` (accepted requirement); only its value changes.

## Risks

- An operator machine with Copier 9.18.2 cannot update a project to this release until it installs 9.19.1; Copier fails explicitly on `_min_copier_version`.
