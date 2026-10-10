## Why

Today a fixable defect in a platform-owned script stops a downstream project until the next immutable release (#420, #425, #427). With the change-class contract in place, a bounded local repair can be allowed safely, but only if it is declared, traceable, regression-tested, temporary, and unable to reach the protected surface. Without detection, a local edit is indistinguishable from silent drift; without a record, it cannot be reviewed, expired or reported upstream.

## What Changes

- A platform-owned release manifest `dev-platform/platform-manifest.json`: sha256 of every plain-copied platform-owned file, generated at release preparation and verified by a platform test against the template tree. Plain files render byte-identically, so the digest is project-independent.
- A project-owned hotfix record file `dev-platform/local-hotfixes.toml` (preserved across Copier updates via `_skip_if_exists`). Each entry names: patched paths, source `platform_version`, the manifest and patched sha256 per path, the defect summary, a regression test path that fails without the patch, the `agent_friction.py` event id, and an explicit statement that the divergence is temporary and not an official release.
- A divergence check `scripts/platform_divergence.py`, run by `platform_doctor.py` and the project's full validation, that fails explicitly when: a manifest path differs from the manifest without a valid record; a record touches a protected path or a path absent from the manifest; a record's `platform_version` differs from the installed one (stale hotfix that must be re-evaluated after the update); a patched sha256 no longer matches; the regression test or friction event reference is missing; or the manifest or protected surface themselves are modified. Its messages state the class (undeclared divergence, protected touch, stale record) and never report a failed check as passed.
- Documentation in `change-classes.md`: the hotfix flow (reproduce, patch inside the allowed boundary, add regression test, record, record friction, ordinary PR with independent review) and its expiry on the next platform update.

## Capabilities

### New Capabilities

- `local-platform-hotfix`: record, manifest, divergence check and flow.

## Impact

New template files (`platform-manifest.json`, `platform_divergence.py`, `local-hotfixes.toml` seed, docs), `platform_doctor.py`, `copier.yml` (`_skip_if_exists`), release preparation script, `dev-platform/checks.toml` full triggers, tests for rendering and Copier update with and without a hotfix. Reuses `agent_friction.py` and the normal PR/CI/review; adds no service, orchestrator or parallel state registry.

## Non-goals

Automatic upstream back-porting of patches; automatic resolution of Copier conflicts when an update meets a hotfix (the check reports a stale record, a human or agent resolves it); hotfixing templated (`.jinja`) files or any protected file; a universal `--force`; changing already published tags.
