# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review against proposal/design/delta spec, local automated validation on the cumulative v1.4.22 release candidate (full unit suite, OpenSpec lifecycle hygiene, strict OpenSpec validation), plus real live-rollout acceptance evidence from the `v1.4.22` managed rollout against `lehard/cuby`.

## Automated validation (cumulative candidate, v1.4.22)

- `python3 -m compileall -q template/scripts scripts` -- passed.
- `python3 scripts/managed_projects.py validate` -- OK (3 managed, 7 candidate, 3 excluded).
- `python3 -m unittest discover -s tests` -- 251 tests passed.
- `python3 template/scripts/openspec_lifecycle.py check` -- OK.
- `npx --yes @fission-ai/openspec@1.6.0 validate --all --strict --no-interactive` -- 12/12 passed.

## Live Cuby acceptance (the closure criterion this change explicitly required)

This change's own closure rule states: "Manual downstream reconciliation is incident recovery, not acceptance evidence. Do not check the Cuby acceptance task merely because a manually repaired PR merged." No manual repair was performed at any point in this acceptance.

Release `v1.4.22` (tag SHA `d18a1e0a111dc5e16d6fae5e1daecee0718b27a3`) automatically dispatched managed rollout (run `31469600804`). The `lehard/cuby -> v1.4.22` job (`93709828214`) is the actual historical acceptance consumer named in this change's proposal:

- `Detect already-pending rollout PR` -- succeeded (via the newly repaired structured helper from `repair-managed-rollout-control-plane`; this step is a precondition for ever reaching Copier preparation and was itself broken until that sibling change landed).
- `Prepare exact-version Copier update` -- succeeded automatically. No `*.rej` file appears anywhere in the resulting PR. This is the exact step this change's recovery logic (exact-target reclaimed-file recovery plus recorded-baseline equivalence) owns.
- A reviewable PR was opened at `lehard/cuby#46` ("chore: update dev-platform to v1.4.22"), with a diff containing only platform-managed paths: `.copier-answers.yml`, `.dev-platform.toml`, `docs/engineering/agent-workflow.md`, `scripts/delegated_write_guard.py` (added), `scripts/delegation_containment.py` (added), `scripts/finish_task.py`, `scripts/project_publish.py`.
- The PR's required downstream `platform-ci` check passed (run `31469681104`).
- The PR was merged through the normal protected workflow: `gh pr merge 46 --repo lehard/cuby --squash`, merge commit `e0cd7edd2b638c5358ad9558b3b4bb6e29d6a6e5`.
- Post-merge, `lehard/cuby`'s `.dev-platform.toml` records `platform_version = "1.4.22"` and `.copier-answers.yml` records `_commit: v1.4.22`, confirmed by reading both files directly from the repository after merge.

No `copier update`/`copier recopy` was run by hand, no `.rej` file was ever produced or deleted by hand, no platform file was manually copied, and neither `.dev-platform.toml` nor `.copier-answers.yml` was hand-edited at any point in this acceptance. The same rollout run also produced normal successful results for `lehard/planner-agent-lab` and `lehard/Jara_Fin`, left untouched per this change's own scope note (stale-PR cleanup is `supersede-stale-managed-rollouts`'s responsibility, not this change's).

## Semantic review

Completeness: PASS. Every implementation task was already checked before this verification; the remaining tasks were exclusively the live-acceptance evidence this note now supplies.

Correctness: PASS. The guarded-recopy proof model (baseline-equivalence against the recorded old platform tag, exact-target reclaimed-file recovery) is unchanged from its already-tested implementation; this verification adds the missing real-world proof that it actually reaches and clears that step end to end, which no unit test alone could demonstrate.

Coherence: PASS. The proposal's stated acceptance bar -- central release dispatches managed rollout normally, Cuby preparation completes without manual intervention, the rollout produces a reviewable PR, and its required CI passes -- is met exactly, with the real run/job/PR/commit evidence recorded above rather than asserted.
