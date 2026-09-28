# Tasks: Copier stable version bump (9.17.0 -> 9.18.2)

- [ ] Re-confirm current stable Copier release and release channel against
      the primary upstream source (PyPI release history / GitHub releases)
      immediately before making the change, in case a newer stable landed
      since authoring.
- [ ] Update `.dev-platform.toml` `[tools.copier]` `min_version` and
      `tested_version` to `9.18.2`.
- [ ] Update `template/.dev-platform.toml.jinja` `[tools.copier]`
      `min_version` and `tested_version` to `9.18.2`.
- [ ] Update `copier.yml` `_min_copier_version` to `"9.18.2"`.
- [ ] Update the `pip install "copier==9.17.0"` line in `.github/workflows/ci.yml`,
      `.github/workflows/publish-version.yml`, `.github/workflows/rollout.yml`,
      and `.github/workflows/adopt-project.yml` to `9.18.2`.
- [ ] Update `template/scripts/platform_doctor.py`'s hardcoded `tools.copier`
      fallback default (`min_version`/`tested_version`) to `9.18.2`.
- [ ] Update the exact-version prose in `README.md`, `docs/managed-rollout.md`,
      and `docs/release-policy.md` to `9.18.2`.
- [ ] Update `tests/test_template_contract.py::test_copier_version_is_explicitly_tested`
      assertions to `9.18.2`.
- [ ] Confirm no in-house workaround for Copier's prior trusted-URL matching
      exists that the upstream fix makes redundant (record the check; remove
      it alongside its tests/docs if one is found).
- [ ] Install/upgrade Copier `9.18.2` locally and run a real
      render/update smoke plus the generated doctor to exercise the
      render/update/adoption/upgrade path without a `.rej` conflict or
      version-mismatch failure.
- [ ] Run `python3 -m compileall -q template/scripts scripts`,
      `python3 -m ruff check scripts template/scripts tests`, and
      `python3 scripts/run_test_groups.py --all`; confirm no regression.
- [ ] Run `python3 template/scripts/openspec_lifecycle.py check`.
- [ ] Record `verification.md` with the checks actually performed (methods,
      not just checkbox counts) and `OpenSpec-Verify: PASS`.
