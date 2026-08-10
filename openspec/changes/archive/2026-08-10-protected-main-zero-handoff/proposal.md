# Change: Protected-main zero-hand-off publication

## Why

After enabling required status checks on `main`, several repositories can no longer complete the existing `publish_mode=direct` lifecycle. The platform currently discovers the mismatch only when the final push is rejected, and `finish_task.py` may already have merged the feature branch into local `main` before that failure. The PR path also requires authenticated GitHub CLI, but this prerequisite is checked late and currently blocks even the branch-push portion of publication.

This is a platform-level mismatch, not a project-specific workaround. A protected integration branch should keep the zero-hand-off agent experience while using GitHub PRs and required checks as the remote merge gate.

## What changes

- Introduce explicit protected-main policy in project configuration.
- Treat `protected_main=true` + `publish_mode=direct` as an invalid configuration and fail in doctor/preflight before implementation or local integration.
- Extend PR publication so a task can complete end-to-end: push feature branch, create/reuse PR, wait for required checks, merge through GitHub, then synchronize local `main` and clean up.
- Keep manual-review PRs possible through an explicit merge policy; zero-hand-off projects use automatic merge after required checks.
- Never merge feature work into local `main` before the remote PR merge succeeds.
- Make GitHub API/CLI authentication a preflight requirement for platform-owned protected-main publication, with a clear one-time remediation message.
- Separate git branch publication from PR API actions so a missing GitHub CLI credential does not hide or lose validated work.
- Update generated guidance and regression tests.
- Roll the new contract out to managed repositories, and adapt project-owned harnesses that currently rely on direct publication.

## Non-goals

- No bypass of required checks or branch protection.
- No force-push to `main`.
- No mandatory human approval for ordinary autonomous task PRs.
- No automatic merge of cross-repository Dev Platform rollout PRs; rollout remains reviewed by default.
- No change to project-owned product-test ownership.

## Success criteria

1. A platform-owned agent can finish a task in a protected-main repository with one lifecycle command and no manual Git hand-off.
2. Required GitHub checks remain authoritative before merge.
3. A missing GitHub credential or incompatible publish configuration is detected by doctor before the task reaches publication.
4. Failed remote publication leaves local `main` unchanged.
5. Cuby, Planner Agent Lab, and Jara_Fin have a completable protected-main publication path after rollout.