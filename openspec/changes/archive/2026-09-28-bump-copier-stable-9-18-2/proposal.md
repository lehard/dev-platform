# Proposal: Bump the tested Copier version to the current stable release

## Why

Dev Platform's pinned/tested Copier version is `9.17.0` (`.dev-platform.toml`,
`template/.dev-platform.toml.jinja`, `copier.yml`, the `.github/workflows/*`
CI installs, and `template/scripts/platform_doctor.py`'s fallback default).
Confirmed against the primary upstream source (PyPI release history,
cross-checked with the `copier-org/copier` GitHub releases changelog) on
2026-09-28, current stable is `9.18.2` (released 2026-09-07), and no
prerelease-only version exists between `9.17.0` and `9.18.2`. The releases
after `9.17.0` are security/reliability fixes to trusted-template
repository-URL handling specifically:

- `9.17.1`: disallow YAML tags in Jinja finalizers; block sandbox escapes
  through path/settings objects.
- `9.17.2`: restrict Jinja template includes and config `!include` paths to
  stay inside the template root; disallow symlink escapes.
- `9.18.0`: prevent trust bypass via encoded URL traversal for alias and
  SCP-style URLs.
- `9.18.2`: prevent trust bypass via ambiguous URL characters (restrict
  trusted-prefix matching to RFC 3986 unreserved characters plus `/`).

This is dependency maintenance, not a new architectural capability: an
ordinary version bump through the platform's existing render/update/rollout
checks, not a parallel in-house security layer on top of Copier.

## What changes

- Raise the pinned/tested Copier version from `9.17.0` to `9.18.2` everywhere
  it is currently recorded:
  - `.dev-platform.toml` (`[tools.copier]` `min_version`/`tested_version`)
  - `template/.dev-platform.toml.jinja` (same fields, rendered for
    new/updated downstream projects)
  - `copier.yml` (`_min_copier_version`)
  - `.github/workflows/ci.yml`, `publish-version.yml`, `rollout.yml`,
    `adopt-project.yml` (`pip install "copier==9.17.0"` -> `9.18.2`)
  - `template/scripts/platform_doctor.py`'s hardcoded `tools.copier` fallback
    default (kept in sync with the pin so an unconfigured project's doctor
    check reflects the same tested version)
  - `README.md`, `docs/managed-rollout.md`, `docs/release-policy.md` prose
    that names the exact tested version
  - `tests/test_template_contract.py::test_copier_version_is_explicitly_tested`
    assertions
- Re-run the existing render/update/adoption/upgrade regression coverage
  against the new pin; no new test surface is introduced.
- Confirm no in-house workaround for Copier's prior trusted-URL matching gaps
  exists in this repository that the upstream fix would make redundant (none
  found in `template/scripts/rollout_identity.py` or
  `scripts/rollout_supersession.py`; those implement this platform's own
  unrelated PR/rollout trust boundary, not a Copier repository-URL
  workaround) -- confirmed, nothing to remove.

## Spec delta

No `openspec/specs/` requirement previously encoded a specific Copier version
number -- `docs/engineering/openspec-workflow.md` only documents the general
"`.dev-platform.toml` records minimum/tested CLI versions" contract. This
change formalizes the existing informal contract already stated in
`docs/release-policy.md` ("the platform tests Copier `X.Y.Z` exactly;
changing the tested version is an explicit platform change") as an `ADDED`
requirement in `specs/platform-config/spec.md`: the platform records one
explicit tested Copier version and keeps every recorded copy of it in
agreement, and bumping it is an explicit, upstream-confirmed platform change.

## Non-goals / exclusions

- Do not update to a prerelease for a newer version number alone.
- Do not add a platform-owned security subsystem on top of Copier when the
  upstream stable fix is sufficient.
- Do not touch unrelated lifecycle behavior.

## Success criteria / verification evidence

- `.dev-platform.toml` and `template/.dev-platform.toml.jinja` `[tools.copier]`
  read `min_version = "9.18.2"` and `tested_version = "9.18.2"`.
- `copier.yml`'s `_min_copier_version` reads `"9.18.2"`.
- All four `.github/workflows/*.yml` install `copier==9.18.2`.
- `template/scripts/platform_doctor.py`'s fallback default matches the new
  pin.
- `python3 -m compileall -q template/scripts scripts`,
  `python3 -m ruff check scripts template/scripts tests`, and
  `python3 scripts/run_test_groups.py --all` pass, including
  `tests/test_template_contract.py::test_copier_version_is_explicitly_tested`
  updated to assert `9.18.2`.
- A real render/update smoke against Copier `9.18.2` (installed locally) and
  the generated doctor succeed without a `.rej` conflict or version-mismatch
  failure, exercising the render/update/adoption/upgrade path named in the
  acceptance evidence.
- `python3 template/scripts/openspec_lifecycle.py check` passes for this
  change.
