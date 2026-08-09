# Tasks

## 1. Immutable/versioned release boundary

- [x] 1.1 Add `platform_ci_ref` to Copier/project config and remove downstream `@main`.
- [x] 1.2 Document append-only release refs and v1 rollout contract.
- [x] 1.3 Create append-only `release-v1.0.0` at validated commit `b4a95a26c7caf14dd5b0d44da0237dcd70bf8715` and never move it.
- [x] 1.4 Pin the new-project/default downstream reusable CI ref to the exact v1 release commit SHA.

## 2. GitHub-aware zero-hand-off lifecycle

- [x] 2.1 Add safe `project_sync.py` and GitHub-aware `agent_doctor.py`.
- [x] 2.2 Add `project_publish.py` with `direct` and `pr` modes; forbid force push/automatic conflict resolution.
- [x] 2.3 Add profile-aware `start_task.py` / `finish_task.py`; retain merge helper compatibility.

## 3. Composable profiles

- [x] 3.1 Add `light`, `standard`, `multi-agent` Copier profiles and capability flags.
- [x] 3.2 Make worktree/board requirements conditional instead of universal.

## 4. OpenSpec contract hardening

- [x] 4.1 Replace false flat source hierarchy with current-spec + active-delta model.
- [x] 4.2 Add no-silent-divergence routing for proposal/specs/design/tasks.
- [x] 4.3 Require `/opsx:verify` before archive for non-trivial changes and distinguish it from structural validation/project QA.
- [x] 4.4 Add minimum/tested OpenSpec version policy and doctor diagnostics.

## 5. Learning/promotion

- [x] 5.1 Add friction event IDs and deliberate sanitized `promote` flow to central GitHub Issues.
- [x] 5.2 Keep raw evidence machine-local and support promotion dry-run.

## 6. Verification

- [x] 6.1 Compile platform scripts and run unit tests locally.
- [x] 6.2 Render all three profiles with Copier and compile generated scripts in PR CI.
- [x] 6.3 Exercise sync/direct-publish safety against temporary Git remotes and verify divergence aborts.
- [x] 6.4 Final code PR CI passed after verification fixes. Semantic verification against the published `/opsx:verify` dimensions is documented in `verification.md`; the literal slash workflow is not invokable from this GitHub connector session and is therefore not falsely claimed as executed.
