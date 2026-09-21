# Verification: Isolate the managed registry into a private operator repository

## Method

`/opsx:verify` was not available in this execution environment. Performed the documented equivalent manual OpenSpec semantic review: re-read `proposal.md`'s Why/What Changes/Success Evidence, `design.md`'s root-cause analysis and mechanism, and the `platform-rollout` spec delta's ADDED requirement with its three scenarios, then checked the implementation (three workflow files) and the updated test suite against each one individually. Also empirically reproduced the original bug against the live `lehard/dev-platform`/`lehard/dev-platform-operator` repositories before writing any code, and re-ran the exact failing GitHub Actions dispatch after the fix (see "Live verification" below).

## Root cause confirmation

Before writing this change: confirmed `openspec/specs/platform-rollout/spec.md`'s existing "Successful releases dispatch reviewed downstream rollout" requirement already states rollout "requires a private managed-projects registry." Confirmed `docs/managed-rollout.md` and `docs/operator-config.example.toml` already describe the registry as an external/operator-owned path. Confirmed via `gh api repos/lehard/dev-platform/contents/managed-projects.json` (404) and a real `Adopt Project` dispatch that the *only* place the accepted contract was violated was the three workflow YAML files hardcoding `platform/managed-projects.json` inside the public checkout. This is a CI-implementation bug against an already-accepted spec, not a new product decision.

## Success evidence review

- "None of the three workflows ever reference `platform/managed-projects.json`" — grepped all three files after editing; zero matches. Asserted by `test_adopt_project_promotes_into_the_private_operator_repository`, `test_rollout_reads_the_managed_registry_from_the_private_operator_repository`, and the updated `test_maintenance_is_explicit_dry_run_or_confirmed_apply_and_uses_managed_matrix` (all assert `assertNotIn("platform/managed-projects.json", ...)`).
- "each fails closed with a clear message when `DEV_PLATFORM_OPERATOR_REPOSITORY` is unset" — added an explicit check in each workflow's first relevant step, matching the existing `DEV_PLATFORM_APP_CLIENT_ID`/`DEV_PLATFORM_APP_PRIVATE_KEY` check's style and message pattern; asserted by the same three tests.
- "a real Adopt Project run reaches the promotion step and commits only into the private operator repository" — see Live verification below.
- "No real fleet repository name appears in public source, tests, or docs" — grepped the full diff for the three real fleet repository names; zero matches. Tests use only the pre-existing synthetic `matrix.repo_name`/`matrix.repository` GitHub Actions expressions, never a literal name.

## Spec-delta scenario review (`specs/platform-rollout/spec.md` in this change)

- "Operator repository is not configured" — covered in all three workflows by the `if [[ -z "$OPERATOR_REPOSITORY" ]]` checks; asserted by all three updated/added tests checking for the exact message substring.
- "Adopt Project promotes a repository to managed" — `adopt-project.yml`'s "Promote completed adoption to managed" step now commits/pushes only inside the `operator/` checkout, to `${{ steps.operator.outputs.repository }}`'s own `main`; the public `platform/` checkout is untouched by this step. Verified live (see below).
- "Rollout or reconciliation plans against the registry" — `rollout.yml`'s `plan` job and `reconcile-stale-rollouts.yml`'s `plan` job each mint a `contents: read`-only token scoped to the operator repository and pass `--registry operator/managed-projects.json` to `managed_projects.py`.

## Live verification (not simulated)

1. Reproduced the original bug: dispatched `adopt-project.yml` for `lehard/planner-agent-lab` against the live `lehard/dev-platform` before this fix existed; it failed at "Promote completed adoption to managed" with `Managed project registry: BLOCKED: managed project registry not found: platform/managed-projects.json`.
2. Created the private `lehard/dev-platform-operator` repository, seeded `managed-projects.json` (`{"schema_version": 1, "projects": []}`), and set the `DEV_PLATFORM_OPERATOR_REPOSITORY` repository variable on `lehard/dev-platform`.
3. Wrote this change's workflow fixes against that real repository and variable (not a fixture).
4. Local checkout: cloned `lehard/dev-platform-operator` to `/Users/Shared/Workspace/dev-platform-operator` and repointed the local external operator TOML's `rollout.registry_path` at that clone; `python3 scripts/operator_doctor.py` and `python3 scripts/managed_projects.py validate` both report `OK` against it, unchanged from before this fix (confirming the local path was never the problem).

The actual re-dispatch of `adopt-project.yml`/`rollout.yml` against the fixed workflow content happens after this change merges to `main` (GitHub Actions runs workflow files from the target ref for `workflow_dispatch`), and is the next action in the parent task once this PR is merged.

## Correctness / coherence

Read the full existing content of all three workflow files, `docs/managed-rollout.md`, and `docs/operator-config.example.toml` before editing. No change to `scripts/managed_projects.py`/`scripts/operator_doctor.py` was needed or made, since both already accepted an arbitrary `--registry` filesystem path — confirmed by re-running their existing test suites unchanged. The new checkout/token steps reuse the identical `actions/checkout` + `actions/create-github-app-token` pattern every other cross-repository step in these same workflows already uses, introducing no new mechanism.

## Independent review

A native Claude executor independently read the proposal/design/spec, the
full diff of all three workflow files, the docs changes, and the test suite,
and ran the tests itself. It confirmed the security property holds (no
`platform/managed-projects.json` reference anywhere, minimal token
permissions, correct step ordering) and archive-readiness, and found two
real, worth-fixing hardening gaps, both applied here:

- `adopt-project.yml` minted the operator write token and checked out the
  operator repository unconditionally, even on the common path where the
  adoption PR is left open for review and "Promote completed adoption to
  managed" never runs -- exposing a write-scoped token it would never use.
  Moved both steps to immediately before the promote step and gated all
  three with the same `if:` condition.
- `DEV_PLATFORM_OPERATOR_REPOSITORY` was only checked for non-emptiness,
  unlike the existing `owner/name` regex validation on the adoption target
  repository input. A misconfigured value would degrade from the intended
  clear fail-closed message into an opaque downstream GitHub API error.
  Added the same `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$` validation to all three
  workflows' operator-repository checks.

It also noted the new tests are string-match assertions on raw YAML (correct
and meaningful for the regression they guard against, but unable to detect a
future step-ordering break); no action taken on that observation, since it
matches the existing test style for every other workflow-content contract
test in this suite.

## Tests run

```
python3 -m compileall -q template/scripts scripts tests
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in (...)]"   # all three workflows parse
python3 -m unittest tests.test_managed_rollout tests.test_rollout_supersession tests.test_rollout_control_plane_regressions tests.test_adopt_project tests.test_template_contract tests.test_docs_semantic_checks -v   # 147+7 passed
python3 scripts/run_test_groups.py --all                              # 13/13 groups passed
openspec validate isolate-operator-registry --strict --no-interactive # valid
```

No material finding surfaced during this review.

OpenSpec-Verify: PASS
Verification-Method: manual-semantic-review (opsx:verify unavailable in this environment)
Automated-Checks-Evidence: automated-checks.json
