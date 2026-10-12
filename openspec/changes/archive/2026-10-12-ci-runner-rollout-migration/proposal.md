## Why

`ci_runner` (BR-503) is merged but unreleased. A project that previously hand-edited `runs-on` of `platform-ci` / `provision` to a self-hosted runner breaks on the first release that contains the question, verified on real Copier 9.18.2:

- A default-answers update keeps the hand-edited `runs-on: my-runner`, records `ci_runner: github-hosted`, and the project's own CI then fails in `platform_doctor` (`runs-on mismatch ... expected 'ubuntu-latest', found 'my-runner'`).
- An update with the self-hosted answers leaves `.rej` files for both workflows. Guarded recopy clears them only for `harness_mode=platform` and only when the committed file is byte-equal to the new render, which it never is because the new render adds the `shared_workspace.py fix` step. `harness_mode=project` gets no such path, and `docs/managed-rollout.md` does not say so.
- The Copier validator accepts `a,,b` and `self hosted`, which `platform_doctor` rejects later in CI.
- `ci_runner` is asked of GitLab projects too, although the doctor skips the check for them.

The break appears on the first release that carries `ci_runner`, so the fix must land before that tag.

## What Changes

- The rollout gets a runner preflight that runs on the rollout branch, before `copier update`, in both harness modes, only when the target template asks `ci_runner`, the project's answers lack it and the project is a GitHub project. It reads the committed `runs-on` of `platform-ci` and `provision`:
  - all `ubuntu-latest` (or the job absent): nothing to do, the default answer is correct;
  - simple labels, equal in every present job, with each customized file equal to its recorded baseline render apart from the `runs-on` value: the rollout records `ci_runner: self-hosted` and `ci_runner_labels`, restores only those `runs-on` lines to the baseline, and commits that on the rollout branch so Copier then applies the new render without conflict;
  - anything else that is not `ubuntu-latest` (expression, group/labels mapping, disagreeing jobs, other edits in the same file, unparseable value): the rollout stops with a message naming the repository, the file and the exact next action.
- The Copier `ci_runner_labels` validator enforces the same rule as `platform_doctor` (no empty entry, no duplicate, `[A-Za-z0-9._-]`), with a parity test.
- `ci_runner` and `ci_runner_labels` are asked only when `scm_provider` is `github`; a GitLab project records neither.
- `docs/managed-rollout.md` describes the migration path, the stop conditions and what to do on a stop, replacing the "record the answers first" instruction.

## Capabilities

### Modified Capabilities

- `ci-safety`: one label rule for Copier and doctor; runner answers apply only to GitHub projects.
- `managed-rollout`: rollout migrates or stops on a hand-edited platform runner.

## Impact

`copier.yml`, `scripts/rollout_project.py`, `template/scripts/platform_doctor.py` (shared rule helper only if needed), `docs/managed-rollout.md`, tests (`tests/test_ci_runner_selection.py`, `tests/test_rollout_recopy.py` or a sibling), platform manifest. No change to rendered workflow templates, `adopt_project`, the guarded-recopy ownership sets or the doctor's mismatch checks.

## Non-goals

Controlled local hotfix mechanism (BR-528); runner choice in `adopt_project` (adoption stays github-hosted); detection of runner configurations beyond simple labels; any change to the project-owned/platform-owned file sets; widening guarded recopy.
