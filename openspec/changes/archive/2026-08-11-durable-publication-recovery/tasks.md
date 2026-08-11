## 1. Build authoritative publication observation

- [x] 1.1 Add a reusable publication observation model for platform-owned PR tasks that derives current state from local Git + remote GitHub: task branch/head SHA, configured base, exact matching PR, required-check state, remote merge/auto-merge state, and whether local reconciliation remains.
- [x] 1.2 Exact PR discovery MUST validate base branch and `headRefOid`; do not identify publication ownership from title/body alone.
- [x] 1.3 Add a concise read-only status renderer/JSON shape with no credentials or raw arbitrary logs.
- [x] 1.4 Add tests for no remote branch, pushed branch/no PR, exact open PR, changed-head PR, merged PR, closed-unmerged PR, and unavailable GitHub state.

## 2. Reconcile publication idempotently

- [x] 2.1 Refactor platform-owned PR publication so normal `finish_task` observes current state and advances the same branch/PR rather than assuming one uninterrupted foreground run.
- [x] 2.2 After create/reuse of an exact-head automatic PR, prefer immediate native GitHub auto-merge / merge-queue arming before a long foreground wait.
- [x] 2.3 Guard every ordinary/auto/queue merge request with the exact validated head SHA using `--match-head-commit` or equivalent expected-head API semantics.
- [x] 2.4 If native auto-merge is unavailable, preserve the existing bounded required-check wait + protected merge fallback; report this as safe but degraded remote durability.
- [x] 2.5 Handle concurrent create/resume races by re-observing and reusing the exact PR instead of creating a long-lived publication lease. Add a short local mutation lock only if a concrete same-host race cannot be absorbed idempotently.
- [x] 2.6 Preserve existing authoritative-`MERGED` behavior and serialized local integration/board/worktree reconciliation.

## 3. Finish/status behavior

- [x] 3.1 Add `finish_task --status` (or an equivalently simple confirmed CLI surface) that is strictly read-only: no push, PR create, merge request, board mutation, cleanup, or local-main mutation.
- [x] 3.2 Make normal `finish_task` the resume path. It SHALL re-run safety validation and then reconcile current remote state; do not add a second resume command unless implementation evidence shows it is necessary.
- [x] 3.3 Detect an existing exact-head open PR before applying first-publication stale-base rejection. Allow that existing PR to continue through GitHub protection/queue when safe; if repository policy requires a branch update and no supported queue path can integrate it, report that concrete blocker without silently changing the candidate SHA.
- [x] 3.4 Update `agent_doctor.py` and generated guidance so unfinished automatic delivery is reported as actionable publication state rather than generic worktree hygiene.

## 4. Native GitHub capability and policy

- [x] 4.1 Detect whether native repository auto-merge/queue capability is available for a platform-owned automatic PR and expose `remote durable` versus `foreground fallback` status.
- [x] 4.2 Do NOT silently modify repository settings from `finish_task`/publisher. Document the explicit administrative command/action to enable native auto-merge when desired.
- [x] 4.3 Add tests proving manual PR mode and `harness_mode=project` remain unchanged.

## 5. Restart, race and safety regression coverage

- [x] 5.1 Add restart/fault-boundary tests simulating caller loss after feature push, after PR creation, after remote auto-merge/queue arming, after GitHub reports `MERGED`, and before local reconciliation; every restart must converge on the same exact task delivery without duplicate PRs or local-main corruption.
- [x] 5.2 Add concurrent publisher tests proving two finish/resume attempts converge on one exact PR and exact-head merge request.
- [x] 5.3 Add changed-head/TOCTOU tests proving a merge request fails closed when the PR head no longer equals the SHA that was validated.
- [x] 5.4 Add a base-advanced existing-PR test and a native-auto-merge-disabled fallback test.
- [x] 5.5 Retain regression coverage for the already-shipped GitHub credential fallback; do not redesign that subsystem in this change.

## 6. Guidance and template coverage

- [x] 6.1 Update generated AGENTS/engineering workflow documentation for GitHub-backed reconciliation, exact-head safety, read-only status, and explicit auto-merge capability setup.
- [x] 6.2 Update template/render/Copier tests for any changed managed scripts/configuration/guidance.
- [x] 6.3 Do not add browser/Playwright discovery work to this change.

## 7. Validate, ship implementation, live-accept, then archive

- [x] 7.1 Run `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 -m unittest discover -s tests -v`, `python3 template/scripts/openspec_lifecycle.py check`, strict OpenSpec validation, and applicable Factory/Copier render-update smoke tests on the exact implementation head.
- [x] 7.2 Publish the implementation through the normal protected-main PR lifecycle while this OpenSpec remains active with the live-acceptance tasks below still incomplete. Do not fabricate verification/archive before downstream acceptance.
  - Done via [PR #111](https://github.com/lehard/dev-platform/pull/111) (`6f52ef8`), merged 2026-08-11T11:06:17Z to protected `main` while this OpenSpec change remained active and 7.3-7.8 stayed unchecked.
- [x] 7.3 Publish the next normal immutable SemVer platform release containing the implementation and let normal managed rollout prepare reviewed exact-version Copier PRs. Merge only the platform-owned consumer rollout PRs needed for acceptance after their downstream CI is green; do not replace or silently modify project-owned harness publication.
  - Release: tag/release [`v1.4.23`](https://github.com/lehard/dev-platform/releases/tag/v1.4.23) at `8f9652d`, published via [PR #116](https://github.com/lehard/dev-platform/pull/116). `publish-version.yml` run [31487469610](https://github.com/lehard/dev-platform/actions/runs/31487469610) created the immutable tag and dispatched `rollout.yml` run [31487481210](https://github.com/lehard/dev-platform/actions/runs/31487481210) (job `lehard/cuby -> v1.4.23`: success).
  - Rollout PR: [lehard/cuby#47](https://github.com/lehard/cuby/pull/47) ("chore: update dev-platform to v1.4.23"), downstream `platform-ci` green (run 31487579588), merged 2026-08-11T11:41:23Z at `.dev-platform.toml` `platform_version = "1.4.23"`.
- [x] 7.4 Perform real remote-durability acceptance in a platform-owned consumer with native GitHub auto-merge explicitly enabled as an administrative setup step: create a validated task PR, confirm remote merge is armed before checks finish, terminate/interrupt the local waiting path, and prove GitHub completes the exact-head merge without that process remaining alive.
  - Administrative step performed by the repository owner (not by this platform, per 4.2): `allow_auto_merge` was explicitly enabled on `lehard/cuby` (confirmed `true` via `gh api repos/lehard/cuby --jq .allow_auto_merge` before this task started; branch protection on `main` — required `platform-ci` status check, `enforce_admins=true`, no force-push/deletion — was independently confirmed unchanged before and is unaffected by this setting).
  - Registered worktree `agent/durable-publication-recovery-accept-2` (board id `0d69a9a795`) with one minimal docs-only commit (`4a5fedf`). `finish_task.py --status` before publishing already reported `merge_durability: "remote_armed_capable"` (vs. `foreground_fallback` in 7.5), confirming the platform detected the new repository capability.
  - `finish_task.py` ran in the background; it pushed the branch and opened [lehard/cuby#49](https://github.com/lehard/cuby/pull/49) at exact head `4a5fedf`. Polling `gh pr view 49 --json autoMergeRequest` showed auto-merge armed (`enabledAt: 2026-08-11T12:20:16Z`, `enabledBy: lehard`) **while** `gh pr checks 49` still reported `platform-ci: pending` — remote merge was armed before checks finished. `finish_task.py --status --json` at that instant reported `"status": "remote_armed"`, `"auto_merge_armed": true`, `"remote_merged": false`.
  - The local `finish_task.py` process was then killed (`TaskStop`, simulating caller/process loss) while auto-merge was armed and checks were still pending; `ps aux` confirmed no local process remained for this task. Polling GitHub only (`gh pr view 49`, no local waiting loop) showed GitHub completed the exact-head merge unattended: `state: MERGED`, `mergedAt: 2026-08-11T12:20:49Z`, merge commit `34f5e71`, with no live local process.
  - A fresh `finish_task.py --status --json` (before any reconciliation) reported `"status": "remote_merged_local_pending"`, `"local_reconciliation_pending": true`, `remote_main_head` ahead of `local_main_head` — read-only, zero mutation (`git status --porcelain` empty, PR count still 1: `gh pr list --head agent/durable-publication-recovery-accept-2 --state all` → `[{"number":49,"state":"MERGED"}]`).
  - Re-running `finish_task.py` printed `Task PR was already merged through GitHub; local main and task state were reconciled without republishing.` — no duplicate PR, no re-merge request, local `main` fast-forwarded to `34f5e71`.
- [x] 7.5 Perform a second real acceptance with native auto-merge unavailable/disabled and prove the safe foreground fallback remains resumable and does not duplicate the PR.
  - In `lehard/cuby` (v1.4.23, `allow_auto_merge=false`, `pr_merge_mode=auto`, multi-agent profile), registered worktree `agent/durable-publication-recovery-accept` (board id `6ac3243060`) with one minimal docs-only commit (`512d892`).
  - First `finish_task.py` run pushed the branch and opened [lehard/cuby#48](https://github.com/lehard/cuby/pull/48) at exact head `512d892`, then was killed (`TaskStop`, simulating caller/process loss) while still inside the bounded required-check wait — PR #48 stayed OPEN, unmerged, at the same head.
  - A second, independent `finish_task.py` invocation printed `PR already exists for exact task head: https://github.com/lehard/cuby/pull/48` (no duplicate PR created), then completed the bounded foreground fallback: `GitHub accepted ordinary squash merge for exact validated head 512d892...`, merge commit `d57b084`, local `main` fast-forwarded and the board entry cleared. `gh pr list --head agent/durable-publication-recovery-accept --state all` shows exactly one PR (#48, MERGED) for this branch across the whole run.
- [x] 7.6 Verify `finish_task --status` accurately reports at least open/checks-pending, remotely armed, merged-awaiting-local-reconciliation, and complete states without mutation.
  - `not_published` (before first publish, 7.5 and 7.4), `open_checks_pending` (7.5, PR #48 open/`pr_relationship=exact_open`), `remote_armed` (7.4, PR #49, `auto_merge_armed: true`, checks still pending), `remote_merged_local_pending` (7.4, PR #49 merged on GitHub but local `main` not yet fast-forwarded, `local_reconciliation_pending: true`), and `complete` (7.5 PR #48 and 7.4 PR #49, `pr_relationship=exact_merged`, `local_main_head==remote_main_head`) were all observed via `finish_task.py --status --json`.
  - `git status --porcelain` / `git log -1` were unchanged by every `--status` invocation across both legs, and the exact-head PR count never exceeded 1 for either branch (`lehard/cuby#48`, `lehard/cuby#49`).
- [x] 7.7 Only after 7.4-7.6 pass, perform semantic OpenSpec verification, record a truthful `OpenSpec-Verify: PASS` receipt and method, archive through the lifecycle helper, rerun full validation, and publish the archive/current-spec update through protected main.
  - Full validation rerun on implementation head `2a4bb4b` (after 7.4/7.6 evidence PR #120 merged): `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 -m unittest discover -s tests -v` (308 tests, OK), `python3 template/scripts/openspec_lifecycle.py check`, `openspec validate --all --strict` — all passed.
  - Semantic verification recorded in `verification.md`; archived via `python3 template/scripts/openspec_lifecycle.py archive durable-publication-recovery`, then published through protected `main`.
- [x] 7.8 Do not cut an additional platform release solely for an archive/spec-only commit if runtime/template code did not change after the already-accepted implementation release.
  - No additional release cut for this archive/spec-only commit: no `template/scripts`, `scripts`, or other runtime/template code changed since `v1.4.23`; only `openspec/` bookkeeping and this archival move.

## Explicitly removed from this change

- No machine-local publication phase database/journal as an authoritative state system.
- No PID/expiry end-to-end publisher lease unless implementation proves an otherwise-unavoidable concrete race.
- No new GitHub authentication design; current validated credential fallback is baseline.
- No browser-QA executable/cache discovery; handle separately only if it remains a demonstrated need.
