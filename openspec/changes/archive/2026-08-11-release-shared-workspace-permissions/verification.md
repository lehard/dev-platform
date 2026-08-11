# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic OpenSpec review plus required platform validation.

## Semantic review

- **Completeness:** `v1.4.25` is a published immutable GitHub release and
  `v1.4.26` is unused. The release change updates only `VERSION` to `1.4.26`
  and retains the existing release workflow's exact-tag rollout dispatch.
- **Correctness:** `publish-version.yml` validates SemVer, refuses to move an
  existing tag, creates a release only for that tag, and dispatches
  `rollout.yml` with the resulting exact tag. The rollout contract targets
  only managed inventory entries and opens reviewed PRs without force-push or
  auto-merge.
- **Coherence:** the change is consistent with the accepted
  `platform-rollout` requirements for immutable releases, exact-version
  Copier updates, inventory allowlisting, and reviewed downstream delivery.
  Post-merge GitHub evidence is recorded on the managed source Issue so the
  archived OpenSpec source contract is not reopened after publication.

## Executed checks

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate` — 3 managed, 7 candidate,
  3 excluded entries; valid.
- `python3 -m unittest discover -s tests -v` — 386 tests passed.
- `python3 template/scripts/openspec_lifecycle.py check`
- `openspec validate release-shared-workspace-permissions --strict --no-interactive`
