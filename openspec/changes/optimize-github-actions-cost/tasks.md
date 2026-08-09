# Tasks

## 1. Shared CI contract

- [ ] 1.1 Update generated Dev Platform workflow triggers so `publish_mode=pr` uses PR + manual dispatch and `publish_mode=direct` uses main-push + manual dispatch.
- [ ] 1.2 Add workflow-level concurrency/cancel-in-progress to ordinary generated validation CI.
- [ ] 1.3 Ensure release publication and managed rollout workflows are not accidentally made cancel-in-progress.
- [ ] 1.4 Update template/render tests to assert both publish-mode trigger variants and concurrency behavior.

## 2. Central dev-platform CI

- [ ] 2.1 Remove automatic post-merge `push: main` execution from central Platform CI; keep PR + manual dispatch.
- [ ] 2.2 Replace the three-runner profile matrix with one runner that executes profile-independent checks once and still exercises light/standard/multi-agent render/update smokes.
- [ ] 2.3 Add concurrency cancellation for superseded Platform CI runs.
- [ ] 2.4 Keep VERSION publication and rollout as separate side-effect workflows.

## 3. Local-heavy / cloud-final contract

- [ ] 3.1 Confirm existing local finish/publish lifecycle still runs the required selected/full checks for each supported workflow profile.
- [ ] 3.2 Update durable docs/generated guidance to state that local verification remains mandatory and cloud CI is the final clean-environment gate/health signal rather than a duplicate full execution layer.
- [ ] 3.3 Add tests or documentation assertions where practical so future template changes do not silently reintroduce PR + post-merge duplicate validation.

## 4. Project-owned high-cost workflow follow-up

These are separate reviewed repository changes because Dev Platform does not own these workflows.

- [ ] 4.1 `Jara_Fin`: add concurrency; make selected PR checks the automatic cloud gate; remove automatic full-suite-on-main and daily scheduled full suite; preserve manual full-suite execution.
- [ ] 4.2 `planner-agent-lab`: make `quality.yml` PR/manual-only with concurrency and no post-merge duplicate; inspect required status checks before deleting/disabling the overlapping legacy `.github/workflows/ci.yml`.
- [ ] 4.3 `etsy`: add concurrency; remove post-merge duplicate; move informational Ruff from `macos-latest` to Linux unless an OS-specific requirement is documented.
- [ ] 4.4 `cuby`: receive the generated Dev Platform CI optimization through the normal managed rollout; no project-specific workflow exists today.
- [ ] 4.5 Record before/after automatic trigger counts for the top-cost repositories so the expected savings are explicit.

## 5. Verification

- [ ] 5.1 Run `python3 -m compileall -q template/scripts scripts`.
- [ ] 5.2 Run `python3 scripts/managed_projects.py validate`.
- [ ] 5.3 Run `python3 -m unittest discover -s tests -v`.
- [ ] 5.4 Run `python3 template/scripts/openspec_lifecycle.py check`.
- [ ] 5.5 Strict-validate OpenSpec with the tested 1.6.0 CLI.
- [ ] 5.6 Render at least PR/direct publish variants and inspect generated workflow YAML.
- [ ] 5.7 Run semantic OpenSpec verification; resolve material findings and record a truthful `verification.md` receipt.

## 6. Publication and rollout

- [ ] 6.1 Archive the verified change through `python3 template/scripts/openspec_lifecycle.py archive optimize-github-actions-cost`.
- [ ] 6.2 Publish a new immutable patch release of Dev Platform.
- [ ] 6.3 Roll the release only to `managed` inventory entries and review the generated PR/diff before merge.
- [ ] 6.4 Do not mutate `candidate`/`excluded` projects through rollout; project-owned workflow PRs from section 4 remain independent reviewed changes.
