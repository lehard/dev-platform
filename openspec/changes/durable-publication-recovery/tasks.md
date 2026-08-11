## 1. Build authoritative publication observation

- [ ] 1.1 Add a reusable publication observation model for platform-owned PR tasks that derives current state from local Git + remote GitHub: task branch/head SHA, configured base, exact matching PR, required-check state, remote merge/auto-merge state, and whether local reconciliation remains.
- [ ] 1.2 Exact PR discovery MUST validate base branch and `headRefOid`; do not identify publication ownership from title/body alone.
- [ ] 1.3 Add a concise read-only status renderer/JSON shape with no credentials or raw arbitrary logs.
- [ ] 1.4 Add tests for no remote branch, pushed branch/no PR, exact open PR, changed-head PR, merged PR, closed-unmerged PR, and unavailable GitHub state.

## 2. Reconcile publication idempotently

- [ ] 2.1 Refactor platform-owned PR publication so normal `finish_task` observes current state and advances the same branch/PR rather than assuming one uninterrupted foreground run.
- [ ] 2.2 After create/reuse of an exact-head automatic PR, prefer immediate native GitHub auto-merge / merge-queue arming before a long foreground wait.
- [ ] 2.3 Guard every ordinary/auto/queue merge request with the exact validated head SHA using `--match-head-commit` or equivalent expected-head API semantics.
- [ ] 2.4 If native auto-merge is unavailable, preserve the existing bounded required-check wait + protected merge fallback; report this as safe but degraded remote durability.
- [ ] 2.5 Handle concurrent create/resume races by re-observing and reusing the exact PR instead of creating a long-lived publication lease. Add a short local mutation lock only if a concrete same-host race cannot be absorbed idempotently.
- [ ] 2.6 Preserve existing authoritative-`MERGED` behavior and serialized local integration/board/worktree reconciliation.

## 3. Finish/status behavior

- [ ] 3.1 Add `finish_task --status` (or an equivalently simple confirmed CLI surface) that is strictly read-only: no push, PR create, merge request, board mutation, cleanup, or local-main mutation.
- [ ] 3.2 Make normal `finish_task` the resume path. It SHALL re-run safety validation and then reconcile current remote state; do not add a second resume command unless implementation evidence shows it is necessary.
- [ ] 3.3 Detect an existing exact-head open PR before applying first-publication stale-base rejection. Allow that existing PR to continue through GitHub protection/queue when safe; if repository policy requires a branch update and no supported queue path can integrate it, report that concrete blocker without silently changing the candidate SHA.
- [ ] 3.4 Update `agent_doctor.py` and generated guidance so unfinished automatic delivery is reported as actionable publication state rather than generic worktree hygiene.

## 4. Native GitHub capability and policy

- [ ] 4.1 Detect whether native repository auto-merge/queue capability is available for a platform-owned automatic PR and expose `remote durable` versus `foreground fallback` status.
- [ ] 4.2 Do NOT silently modify repository settings from `finish_task`/publisher. Document the explicit administrative command/action to enable native auto-merge when desired.
- [ ] 4.3 Add tests proving manual PR mode and `harness_mode=project` remain unchanged.

## 5. Restart, race and safety regression coverage

- [ ] 5.1 Add restart/fault-boundary tests simulating caller loss after feature push, after PR creation, after remote auto-merge/queue arming, after GitHub reports `MERGED`, and before local reconciliation; every restart must converge on the same exact task delivery without duplicate PRs or local-main corruption.
- [ ] 5.2 Add concurrent publisher tests proving two finish/resume attempts converge on one exact PR and exact-head merge request.
- [ ] 5.3 Add changed-head/TOCTOU tests proving a merge request fails closed when the PR head no longer equals the SHA that was validated.
- [ ] 5.4 Add a base-advanced existing-PR test and a native-auto-merge-disabled fallback test.
- [ ] 5.5 Retain regression coverage for the already-shipped GitHub credential fallback; do not redesign that subsystem in this change.

## 6. Guidance and template coverage

- [ ] 6.1 Update generated AGENTS/engineering workflow documentation for GitHub-backed reconciliation, exact-head safety, read-only status, and explicit auto-merge capability setup.
- [ ] 6.2 Update template/render/Copier tests for any changed managed scripts/configuration/guidance.
- [ ] 6.3 Do not add browser/Playwright discovery work to this change.

## 7. Validate, ship implementation, live-accept, then archive

- [ ] 7.1 Run `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 -m unittest discover -s tests -v`, `python3 template/scripts/openspec_lifecycle.py check`, strict OpenSpec validation, and applicable Factory/Copier render-update smoke tests on the exact implementation head.
- [ ] 7.2 Publish the implementation through the normal protected-main PR lifecycle while this OpenSpec remains active with the live-acceptance tasks below still incomplete. Do not fabricate verification/archive before downstream acceptance.
- [ ] 7.3 Publish the next normal immutable SemVer platform release containing the implementation and let normal managed rollout prepare reviewed exact-version Copier PRs. Merge only the platform-owned consumer rollout PRs needed for acceptance after their downstream CI is green; do not replace or silently modify project-owned harness publication.
- [ ] 7.4 Perform real remote-durability acceptance in a platform-owned consumer with native GitHub auto-merge explicitly enabled as an administrative setup step: create a validated task PR, confirm remote merge is armed before checks finish, terminate/interrupt the local waiting path, and prove GitHub completes the exact-head merge without that process remaining alive.
- [ ] 7.5 Perform a second real acceptance with native auto-merge unavailable/disabled and prove the safe foreground fallback remains resumable and does not duplicate the PR.
- [ ] 7.6 Verify `finish_task --status` accurately reports at least open/checks-pending, remotely armed, merged-awaiting-local-reconciliation, and complete states without mutation.
- [ ] 7.7 Only after 7.4-7.6 pass, perform semantic OpenSpec verification, record a truthful `OpenSpec-Verify: PASS` receipt and method, archive through the lifecycle helper, rerun full validation, and publish the archive/current-spec update through protected main.
- [ ] 7.8 Do not cut an additional platform release solely for an archive/spec-only commit if runtime/template code did not change after the already-accepted implementation release.

## Explicitly removed from this change

- No machine-local publication phase database/journal as an authoritative state system.
- No PID/expiry end-to-end publisher lease unless implementation proves an otherwise-unavoidable concrete race.
- No new GitHub authentication design; current validated credential fallback is baseline.
- No browser-QA executable/cache discovery; handle separately only if it remains a demonstrated need.
