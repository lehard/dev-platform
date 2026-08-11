# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic OpenSpec review (no `/opsx:verify` tool integration available in this agent environment) plus real GitHub live-acceptance evidence in a platform-owned consumer, both auto-merge-disabled and auto-merge-enabled

## Scope reviewed

Reviewed proposal, design, delta requirements (`platform-lifecycle`, `publication-recovery`, `completion-lifecycle`), tasks, `publication_state.py`/`finish_task.py`/`project_publish.py`/`agent_doctor.py`, the platform unit suite, and two independent live runs of the actual published lifecycle in `lehard/cuby` for completeness, correctness, and coherence.

## Platform evidence

Implementation head `6f52ef8` (PR #111) plus subsequent bookkeeping/evidence commits, most recently `2a4bb4b`, passed:

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 -m unittest discover -s tests -v` — 308 tests, OK
- `python3 template/scripts/openspec_lifecycle.py check`
- `openspec validate --all --strict` — 12/12 items passed, including `change/durable-publication-recovery` and `change/adopt-gh-aw-process-automation`

## Coherence with other active changes

`adopt-gh-aw-process-automation` also modifies `platform-lifecycle`, but its delta only touches the unrelated "Deliberate learning promotion" requirement and adds a new "Meaningful friction capture is a completion invariant" requirement. No requirement name or scenario collides with this change's additions (PR reconciliation, exact-head merge guards, read-only status, race convergence, native auto-merge visibility). Both deltas are additive and can land in the same `platform-lifecycle` spec without conflict.

## Live-acceptance evidence (real GitHub, not simulated)

Release: `v1.4.23` (tag/release, PR #116), rolled out to `lehard/cuby` via reviewed Copier PR #47 (downstream `platform-ci` green before merge).

**Foreground fallback** (`lehard/cuby`, `allow_auto_merge=false`): `finish_task.py` opened [cuby#48](https://github.com/lehard/cuby/pull/48) at exact head `512d892`, was killed mid required-check wait (`TaskStop`, simulating caller loss), left the PR open/unmerged at the same head. A fresh `finish_task.py` invocation printed `PR already exists for exact task head` (no duplicate), then completed via the bounded protected-merge fallback (merge commit `d57b084`).

**Native auto-merge** (`lehard/cuby`, `allow_auto_merge` explicitly enabled by the repository owner as an administrative step, per Requirement "Native automatic-merge capability is visible and explicitly administered" — the platform never toggled this itself): `finish_task.py` opened [cuby#49](https://github.com/lehard/cuby/pull/49) at exact head `4a5fedf`; GitHub reported auto-merge armed (`gh pr view --json autoMergeRequest`) while `platform-ci` was still `pending`, matching the "Auto-merge is armed before required checks finish" scenario. The local process was then killed while armed; polling GitHub only (no local wait loop, confirmed via `ps aux`) showed the exact-head merge completed unattended (`mergedAt` after the kill, merge commit `34f5e71`). A fresh `finish_task.py` reconciled local `main` without republishing ("already merged through GitHub").

`finish_task.py --status --json` was independently confirmed read-only (`git status --porcelain` empty, identical `git log -1` before/after) across all four required states: `not_published`, `open_checks_pending`, `remote_armed`, `remote_merged_local_pending`, and `complete`. Branch protection on `lehard/cuby` `main` (required `platform-ci` status check, `enforce_admins=true`, no force-push/deletion) was confirmed unchanged before the native-auto-merge leg ran — only `allow_auto_merge` changed, and only by the repository owner.

## Findings

No material semantic divergence between the active change and the reviewed implementation. Both the foreground-fallback and native-auto-merge remote-durability paths behave exactly as specified, including exact-head guarding, idempotent resume with zero duplicate PRs, and accurate read-only status reporting with zero mutation. No repository setting was ever mutated by the platform itself; the one administrative setting change (`allow_auto_merge`) was made explicitly by the repository owner outside this platform's control, as the spec requires.
