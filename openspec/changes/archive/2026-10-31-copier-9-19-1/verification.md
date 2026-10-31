OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the platform-config delta, proposal, design and tasks; upstream confirmation from PyPI (`copier` latest 9.19.1) and the upstream CHANGELOG at tag v9.19.1; Copier smokes and a render/update/rollback proof with Copier 9.19.1 from an isolated virtualenv (machine-wide Copier 9.18.2 unchanged); targeted tests; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Upstream (2026-10-30)

PyPI latest `copier` 9.19.1. CHANGELOG: v9.19.1 (2026-10-13) restores Git older than 2.43.1; v9.19.0 (2026-10-12) Security: prevent argument injection via `git` subprocess calls; Fix: keep symlink targets when a directory containing a symlink is renamed; Feat: opt-in questions via `ask` (not used by the template). No prerelease.

## Completeness

- Every recorded copy says 9.19.1: `copier.yml` `_min_copier_version`, `template/.dev-platform.toml.jinja` `[tools.copier]`, the Copier installs in `ci.yml`, `adopt-project.yml`, `lifecycle-workers.yml`, `publish-version.yml`, `rollout.yml`, `platform_doctor.py`'s default, `docs/release-policy.md`, `docs/managed-rollout.md`, README and three Explorer nodes (marked reviewed); `tests/test_template_contract.py` asserts the agreement (85 passed with the doctor tests).
- Smokes with Copier 9.19.1 on PATH: `tests/project_harness_adoption_smoke.py` passed (mature multi-agent adoption); `tests/rollout_recopy_smoke.py` skipped by its documented rule (historical tag v1.2.3 absent from this history).
- Render/update/rollback proof in a group-shared temporary directory: render v3.0.0 with Copier 9.18.2, add a project-owned README line, commit; `copier update` to the change head with 9.19.1 exits 0, no `.rej`, the project-owned line kept, `_commit` advanced; Copier 9.18.2 against the new template fails explicitly ("requires Copier version >= 9.19.1"); rollback: `git revert` of the update commit restores `_commit: v3.0.0` and Copier 9.18.2 `update --vcs-ref v3.0.0` exits 0. A fresh render with 9.19.1 records `[tools.copier]` 9.19.1.

## Not verified / limits

- Git subprocess argument safety and symlink-rename behavior are upstream fixes; they are not re-tested here beyond the smokes.
- Operator steps outside the repository: install Copier 9.19.1 where Copier runs locally, and set the untracked operator `.dev-platform.toml` `[tools.copier]` to 9.19.1 (machine-local; the accepted requirement lists `.dev-platform.toml` among the copies).
- `docs/engineering/upstream-evaluations/teamai.md` keeps its dated evaluation note naming Copier 9.18.2.
- #528 (local hotfix preservation) is untouched.
- Existing fallback reported, not changed: `platform_doctor.py` defaults `[tools.copier]` for a project without that table, as the accepted requirement specifies.
- Independent review: ready; one spec-fidelity advisory, listed in its review file.
- The selected checks ran with `copier` 9.19.1 resolved from the isolated virtualenv through a PATH entry holding only that executable (Python unchanged); with the machine-wide Copier 9.18.2 the template-rendering tests fail as intended ("This template requires Copier version >= 9.19.1"). CI installs 9.19.1 itself; a local machine needs the owner's install.
