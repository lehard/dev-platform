## Why

`template/.github/workflows/dev-platform.yml.jinja` and `process-health-labels.yml.jinja` hard-code `runs-on: ubuntu-latest`. A downstream project that runs its checks on a self-hosted runner (kamenkadmitry/ai_assist_content#99, runner `alters`) can only hand-edit these platform-owned files. The next guarded rollout then either blocks on the byte-sensitive ownership check or, after reconciliation, renders `ubuntu-latest` again and silently moves the project's CI out of its real environment. On a self-hosted runner `platform_doctor` also enforces shared-workspace invariants, so the project had to add `shared_workspace.py fix` before the doctor by hand, and the label-provisioning job failed because the runner has no `gh` CLI.

## What Changes

- New Copier questions `ci_runner` (`github-hosted` | `self-hosted`, default `github-hosted`) and `ci_runner_labels` (comma-separated labels, asked and required only for `self-hosted`).
- Platform-rendered GitHub Actions jobs (`platform-ci`, `provision`) render `runs-on` from the answer: `ubuntu-latest` for GitHub-hosted, the declared label (or label list) for self-hosted.
- For self-hosted runners `platform-ci` renders `python3 scripts/shared_workspace.py fix` before `platform_doctor`.
- The label-provisioning job calls the GitHub REST API with `curl` instead of `gh`, so it runs on any runner with no extra tooling.
- `platform_doctor` verifies that the committed workflow's runner and preparation step agree with the recorded answers and that self-hosted labels are present and well formed; a mismatch or missing answer fails explicitly.
- Rollout documentation describes how a project that hand-edited its runner records the equivalent answer before the next rollout.

## Capabilities

### Modified Capabilities

- `ci-safety`: the rendered platform workflow runner is a declared project answer checked by the doctor.

## Impact

`copier.yml`, `template/.github/workflows/dev-platform.yml.jinja`, `template/.github/workflows/process-health-labels.yml.jinja`, `template/scripts/platform_doctor.py` (and its `scripts/` mirror if present), tests for render/update/doctor, `docs/release-policy.md` or `docs/managed-rollout.md`. On Copier update an existing project records the new answers (an accepted default records `github-hosted`, which renders `ubuntu-latest`); `platform_doctor` fails explicitly when the recorded `ci_runner` answer is missing.

## Non-goals

Changing which checks PR CI runs, conditional doctor, splitting cloud and machine-local doctor invariants (#470, #368), runners for project-owned workflows, releasing or rolling out.
