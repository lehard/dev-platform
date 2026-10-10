## 1. Manifest

- [x] 1.1 Generate `template/dev-platform/platform-manifest.json` in the release preparation step and add a platform test that compares it to the template tree.

## 2. Record and check

- [x] 2.1 Define the `local-hotfixes.toml` schema, seed an empty file, add it to `copier.yml` `_skip_if_exists`.
- [x] 2.2 Implement `template/scripts/platform_divergence.py` with the explicit failure classes of the spec; wire it into `platform_doctor.py` and the full-validation triggers in `dev-platform/checks.toml`.

## 3. Documentation

- [x] 3.1 Document the hotfix flow and expiry in `change-classes.md`; keep root `AGENTS.md` as pointers only.

## 4. Tests

- [x] 4.1 Valid hotfix passes; undeclared divergence, protected touch, unknown path, stale version, digest mismatch, missing regression test and missing/unreadable friction reference each fail with their class.
- [x] 4.2 Representative end-to-end: a reproducible defect in a hotfixable script of an installed project is fixed locally with regression evidence and passes the check without a new release.
- [x] 4.3 Copier: new-project render and existing-project update with and without a hotfix; record preserved.

## 5. Verification and delivery

- [ ] 5.1 Required platform checks, truthful semantic verification, archive, retrospectives, publication.
