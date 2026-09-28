# Verification receipt

Verification-Method: documented semantic OpenSpec review plus automated platform checks
Automated-Checks-Evidence: automated-checks.json

## Semantic review

Confirmed against the primary upstream sources on 2026-09-28: PyPI's release
history (`https://pypi.org/pypi/copier/json` and the PyPI history page) and
the `copier-org/copier` GitHub releases changelog. Current stable is
`9.18.2` (2026-09-07), with no newer prerelease pending; the releases since
`9.17.0` (`9.17.1`, `9.17.2`, `9.18.0`, `9.18.2`) are the trust-boundary /
repository-URL security fixes the issue names as the reason for the bump.

Located every recorded copy of the tested Copier version and updated all of
them to `9.18.2`: `.dev-platform.toml` (untracked/local-only in this
checkout -- the portable source of truth is `template/.dev-platform.toml.jinja`,
which is tracked and updated), `copier.yml`'s `_min_copier_version`, all four
`.github/workflows/*.yml` Copier installs, `template/scripts/platform_doctor.py`'s
hardcoded `tools.copier` fallback default, and the exact-version prose in
`README.md`, `docs/managed-rollout.md`, and `docs/release-policy.md`. Updated
`tests/test_template_contract.py::test_copier_version_is_explicitly_tested`'s
assertions to match. Added `specs/platform-config/spec.md` as an `ADDED`
requirement formalizing the existing informal "one exact tested version,
kept in agreement, bumped only as an explicit platform change" contract
already stated in `docs/release-policy.md` prose, since no prior
`openspec/specs/` requirement encoded it and the OpenSpec schema requires at
least one specs/ delta per managed change.

Checked for an in-house workaround for Copier's prior trusted-URL matching
gaps that the upstream fix would make redundant: `template/scripts/rollout_identity.py`
and `scripts/rollout_supersession.py` both use the phrase "trust boundary"
but implement this platform's own GitHub PR/rollout-ownership trust boundary
(reserved branch name, base branch, bot identity) -- unrelated to Copier's
template-source repository-URL matching. Nothing to remove.

`check_tool_version`'s version-tuple parsing (`re.search(r"(\d+)\.(\d+)\.(\d+)")`)
is unaffected by the new literal; `9.18.2` matches the same pattern as
`9.17.0`.

### Verification limitation: local live-render smoke

Installed Copier `9.18.2` locally (upgraded from `9.17.0`) and attempted a
real `copier copy`/`copier update` render against this checkout, matching
the render/update/adoption/upgrade path named in the issue's acceptance
evidence. This consistently failed inside Copier's own internal temporary
local clone with `dunamai.DunamaiError` / `fatal: revision walk setup
failed` while resolving the template's dynamic Git-tag version, referencing
a commit object (`5e59f174...`) that does not exist on the `origin` remote
(`git fetch origin <sha>` returns "not our ref") and is not referenced by
any local ref, packed-ref, or reflog in this checkout. The failure
reproduces identically against `--vcs-ref v1.5.8` (an unrelated historical
tag) and against `--vcs-ref HEAD` both before and after this change's
commit, and running the exact same `git for-each-ref --merged` command
Copier/dunamai issues internally succeeds when run directly in this
worktree. This isolates the failure to Copier's own local-clone mechanism
interacting with this sandbox's shared, shallow, multi-worktree Git object
store -- not to the content of this change -- but it means the live
render/update/doctor smoke could not be completed from this environment.
Reported as a limitation rather than fabricated; the equivalent deterministic
coverage below (including `tests/test_template_contract.py`'s exact-string
assertions on every pinned location, and the wider platform-bootstrap /
rollout / adoption test groups that exercise `platform_doctor.py`'s version
logic without a live Copier binary) is the actual verification evidence for
this change. Real CI, which checks out a complete (non-shallow, single
worktree) clone, is the recommended authoritative confirmation of the live
render/update path before merge.

## Checks performed

- `python3 -m compileall -q template/scripts scripts` -- passed.
- `python3 -m ruff check scripts template/scripts tests` -- passed.
- `python3 -m unittest tests.test_template_contract.TemplateContractTests.test_copier_version_is_explicitly_tested` -- passed.
- `python3 scripts/run_test_groups.py --all` (`DEV_PLATFORM_TEST_JOBS=3`) -- all 13 groups passed, 1,380 declared/discovered tests.
- `python3 scripts/managed_projects.py validate` -- passed.
- `openspec validate bump-copier-stable-9-18-2 --strict` -- passed.
- `python3 template/scripts/openspec_lifecycle.py check` -- passed before archive readiness.

`openspec verify` is not provided by the installed OpenSpec CLI, so the
documented equivalent semantic review above is the verification method.

OpenSpec-Verify: PASS
