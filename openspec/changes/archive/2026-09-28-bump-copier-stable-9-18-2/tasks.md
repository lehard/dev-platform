# Tasks: Copier stable version bump (9.17.0 -> 9.18.2)

- [x] Re-confirm current stable Copier release and release channel against
      the primary upstream source (PyPI release history / GitHub releases)
      immediately before making the change, in case a newer stable landed
      since authoring. Confirmed 2026-09-28: `9.18.2` (2026-09-07) remains
      current stable, no newer prerelease.
- [x] Update `template/.dev-platform.toml.jinja` `[tools.copier]`
      `min_version` and `tested_version` to `9.18.2` (also updated the local,
      untracked root `.dev-platform.toml` used by this checkout's own
      lifecycle tooling; it is excluded from git per `.git/info/exclude` and
      is not part of the committed platform contract).
- [x] Update `copier.yml` `_min_copier_version` to `"9.18.2"`.
- [x] Update the `pip install "copier==9.17.0"` line in `.github/workflows/ci.yml`,
      `.github/workflows/publish-version.yml`, `.github/workflows/rollout.yml`,
      and `.github/workflows/adopt-project.yml` to `9.18.2`.
- [x] Update `template/scripts/platform_doctor.py`'s hardcoded `tools.copier`
      fallback default (`min_version`/`tested_version`) to `9.18.2`.
- [x] Update the exact-version prose in `README.md`, `docs/managed-rollout.md`,
      and `docs/release-policy.md` to `9.18.2`.
- [x] Update `tests/test_template_contract.py::test_copier_version_is_explicitly_tested`
      assertions to `9.18.2`.
- [x] Confirm no in-house workaround for Copier's prior trusted-URL matching
      exists that the upstream fix makes redundant (record the check; remove
      it alongside its tests/docs if one is found). Checked
      `template/scripts/rollout_identity.py` and
      `scripts/rollout_supersession.py`; both implement this platform's own
      unrelated PR/rollout trust boundary. Nothing to remove.
- [x] Install/upgrade Copier `9.18.2` locally and attempt a real
      render/update smoke plus the generated doctor. Blocked by a
      pre-existing sandbox limitation unrelated to this change's content
      (Copier's internal temporary local clone cannot resolve the
      template's dynamic Git-tag version against this shared, shallow,
      multi-worktree checkout -- reproduces identically against an
      unrelated historical tag and against HEAD both before and after this
      change). Documented as a verification limitation in `verification.md`
      rather than skipped silently; relied on the deterministic test
      coverage below instead, including `platform_doctor.py`'s version
      logic exercised by the platform-bootstrap/rollout/adoption test
      groups without a live Copier binary.
- [x] Run `python3 -m compileall -q template/scripts scripts`,
      `python3 -m ruff check scripts template/scripts tests`, and
      `python3 scripts/run_test_groups.py --all`; confirm no regression.
      All passed (13 groups, 1,380 tests).
- [x] Run `python3 template/scripts/openspec_lifecycle.py check`. Passed.
- [x] Record `verification.md` with the checks actually performed (methods,
      not just checkbox counts) and `OpenSpec-Verify: PASS`.
