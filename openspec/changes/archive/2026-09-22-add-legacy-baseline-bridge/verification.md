# Verification: Bridge a pre-cutover legacy baseline into Copier's mirror cache during rollout

## Method

`/opsx:verify` was not available in this execution environment. Performed the documented equivalent manual OpenSpec semantic review: re-read `proposal.md`'s Why/What Changes/Success Evidence, `design.md`'s root-cause analysis and mechanism, and the `platform-rollout` spec delta's ADDED requirement with its five scenarios, then checked the implementation (`scripts/rollout_project.py`, `.github/workflows/rollout.yml`, `docs/managed-rollout.md`) and the test suite against each one individually.

## Root cause confirmation

Before writing this change: reproduced the failure live by dispatching `Roll Out Platform` for `lehard/planner-agent-lab` (`v1.4.38 -> v1.5.1`) against the real `lehard/dev-platform`; it failed at `copier update` with `fatal: invalid reference: v1.4.38`. Confirmed the exact cache-path algorithm by calling `copier._vcs.get_repo`/`_get_or_create_mirror` directly against `gh:lehard/dev-platform` and matching the SHA256 hash in the failure log byte-for-byte. Confirmed empirically, before writing any workflow/source change, that a naive tag injection into that mirror is deleted by Copier's own `git remote update --prune` refresh on the next cache touch, and that narrowing the mirror's `origin` fetch refspec first makes an injected tag immune to that prune (real `git`, real `copier`, real cloned repositories).

## Success evidence review

- "A managed project still on a pre-cutover baseline tag can complete a real `copier update --vcs-ref <post-cutover version>` through the normal rollout path when `DEV_PLATFORM_LEGACY_REPOSITORY` is configured, with no `.rej` files" — covered by `LegacyBaselineBridgeTests` in `tests/test_rollout_recopy.py`, which exercises the real narrow-then-fetch command sequence against mocked `copier._vcs` internals with real argument values.
- "A project already on a post-cutover baseline never triggers a legacy fetch" — `test_ensure_legacy_baseline_skips_the_fetch_when_the_tag_already_resolves`.
- "Nothing is pushed to, or rewritten in, the canonical or legacy repository" — the implementation only ever calls `git fetch`/`git config`/`git rev-parse` against the local mirror and platform checkout; no `push` call exists anywhere in the new code.
- "Unset behaves exactly as before this change" — `test_ensure_legacy_baseline_is_a_no_op_without_a_configured_repository` and `test_ensure_platform_tag_available_reports_both_failures_without_legacy_configured_or_matching`.

## Spec-delta scenario review (`specs/platform-rollout/spec.md` in this change)

- "Project's recorded baseline predates the canonical history" — `test_ensure_legacy_baseline_narrows_refspec_then_fetches_from_legacy` pins the exact 4-command sequence (unset-all, add heads refspec, add version-tag refspec, fetch from legacy with `--no-tags`).
- "Project is already on a post-cutover baseline" — see above.
- "Legacy repository is not configured" — see above.
- "Guarded-recopy's own baseline comparison needs the same pre-cutover tag" — `test_ensure_platform_tag_available_falls_back_to_legacy_repository`.
- "A malformed legacy repository is rejected" — new `test_ensure_platform_tag_available_rejects_a_malformed_legacy_repository` and `test_ensure_legacy_baseline_rejects_a_malformed_legacy_repository`, added after independent review (see below).

## Scope discipline

Confirmed via `git diff main..HEAD --stat` that this change touches only `scripts/rollout_project.py`, `.github/workflows/rollout.yml`, `docs/managed-rollout.md`, and the two rollout test files, plus its own OpenSpec package. No change to `.copier-answers.yml` schema, `scripts/managed_projects.py`, or the private operator registry, matching `design.md`'s explicit out-of-scope list.

## Independent review

A native Claude executor (general-purpose subagent) independently read the proposal/design/spec and the full diff, read Copier 9.17.1's actual installed source to verify the mirror-cache mechanics claims rather than trusting `design.md`'s prose, confirmed no `actions/cache` step persists `~/.cache/copier` across `rollout.yml` matrix jobs (so the narrowed-refspec-is-never-restored limitation is safe today), and ran the tests itself (`pytest tests/test_rollout_recopy.py tests/test_managed_rollout.py -q`: 61 passed, 6 pre-existing unrelated skips). It reported no blockers and one real, worth-fixing gap, applied here:

- `legacy_repository` was spliced unvalidated into a `git fetch` URL (`scripts/rollout_project.py`, both call sites) and `rollout.yml`'s new variable had no format check, unlike the codebase's own established `DEV_PLATFORM_OPERATOR_REPOSITORY` precedent (`^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`, validated in both `rollout.yml` and `scripts/managed_projects.py`). A malformed value could redirect the fetch to an attacker-chosen host. Added `validated_legacy_repository()` in `scripts/rollout_project.py`, called at both call sites, plus the same regex check in `rollout.yml`'s bash step; added regression tests for both.

It also flagged three nits, all addressed:
- `copier_vcs.get_repo(...)` wasn't covered by the same `AttributeError` guard as `_get_or_create_mirror` despite the docstring treating both as equally fragile private APIs — tightened.
- The spec delta didn't cover the second, mechanically distinct fallback in `ensure_platform_tag_available` (used by guarded-recopy) even though it was implemented and tested — added a scenario for it (and for the new validation-failure behavior).
- The narrowed mirror refspec is never restored, with safety depending on CI runners being ephemeral — documented as an explicit, currently-true constraint in `design.md`'s out-of-scope section, flagged for revisiting if template-source caching is ever added to `rollout.yml`.

## Tests run

```
python3 -m compileall -q template/scripts scripts
python3 scripts/run_test_groups.py --all        # 13/13 groups passed, 1140 tests
openspec validate add-legacy-baseline-bridge --strict   # valid
python3 -m pytest tests/test_rollout_recopy.py tests/test_managed_rollout.py -q   # independent review's own run: 61 passed, 6 pre-existing skips
```

## Real CI failure found and fixed during publication

The PR's own `Platform CI` run (not simulated locally: local runs always have `copier` already installed from prior work in this environment) failed the required `validate` check: the new `LegacyBaselineBridgeTests` tests patch `copier._vcs.get_repo`/`_get_or_create_mirror`, which requires the real `copier` package to be importable, but `.github/workflows/ci.yml`'s "Unit tests" step ran before its existing "Install tested Copier" step (which previously only existed for the later template-rendering smoke tests). Fixed by moving "Install tested Copier" immediately before "Unit tests" in `ci.yml`. Re-ran the full local suite after the reorder (13/13 groups, 1140 tests, unchanged) and re-validated the YAML parses; the corrected PR CI run is the actual terminal proof this fix is real (see the PR).

No unresolved finding remains.

OpenSpec-Verify: PASS
Verification-Method: manual-semantic-review (opsx:verify unavailable in this environment)
Automated-Checks-Evidence: automated-checks.json
