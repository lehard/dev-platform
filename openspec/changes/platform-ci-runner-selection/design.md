## Context

- `copier.yml` defines downstream answers; `.copier-answers.yml` records them and Copier reuses recorded answers on update. `.dev-platform.toml` is `_skip_if_exists` and guarded rollout refuses project-contract changes beyond `platform_version`, so a new runner setting cannot live there for existing projects.
- `platform_doctor.check_rendered_workflow_mode` already proves that the committed workflow agrees with `publish_mode`; the doctor already reads `.copier-answers.yml`.
- Guarded rollout treats platform-owned workflows as byte-sensitive ownership checks (platform-rollout spec), so a hand-edited runner blocks rollout until reconciled.
- The downstream hand edit (`47556aa`) uses `runs-on: alters`, a `Repair shared-workspace permissions on self-hosted runners` step running `python3 scripts/shared_workspace.py fix` between capability sync and doctor, and a `curl`-based label provisioning job.

## Decisions

1. **Two answers, explicit kind.** `ci_runner` chooses `github-hosted` or `self-hosted`; `ci_runner_labels` is asked only for `self-hosted`. Inferring the kind from label names (`ubuntu-*` etc.) is rejected as fragile. The Copier validator rejects an empty label list for `self-hosted`; the doctor additionally enforces the label grammar `[A-Za-z0-9._-]+` per comma-separated entry, no empty entries, no duplicates.
2. **Rendering.** GitHub-hosted renders `runs-on: ubuntu-latest` exactly as today (byte-identical output for existing projects). Self-hosted with one label renders `runs-on: <label>`; several labels render a YAML flow list `runs-on: [a, b]`. Both platform-rendered jobs use the same answer.
3. **Self-hosted preparation.** Self-hosted `platform-ci` renders the shared-workspace repair step between capability sync and doctor, with the same name and command as the downstream edit, so an equivalent answer renders the downstream file byte-for-byte where the edit matches.
4. **Portable label provisioning.** The provisioning job uses `curl` against the GitHub REST API for both runner kinds (same text as the downstream edit), removing the hidden `gh` dependency rather than branching on runner kind.
5. **Doctor agreement check.** A new doctor check reads the recorded answers. A rendered GitHub project whose answers lack `ci_runner` fails explicitly (Copier records every answered question including defaults on copy/update, so absence means the answers file was edited or predates the template that renders this check). The committed `platform-ci` runner and the presence/absence of the repair step must match the answer; a mismatch fails naming the expected and found values. GitLab projects are unaffected. It compares both platform-rendered runners: `platform-ci` in `dev-platform.yml` (with the self-hosted repair step) and `provision` in `process-health-labels.yml`, which must exist. The check does not apply to GitLab projects (no GitHub workflow is rendered) or to the platform source checkout (`platform_version = "source"`), which is not a rendered project and records no Copier answers.
6. **Migration.** A project that hand-edited its runner records `ci_runner: self-hosted` and `ci_runner_labels: <labels>` in `.copier-answers.yml` (or passes them as Copier data) before the rollout that introduces this version; the rollout then renders an equivalent workflow instead of conflicting. Documented in rollout guidance; no automatic detection of hand edits.

## Risks

- Existing projects must render byte-identical GitHub-hosted workflows: covered by a render test against the current output.
- A missed migration step for a self-hosted project still renders `ubuntu-latest`; the existing byte-sensitive ownership check blocks the rollout on the hand-edited file, so the reset is not silent. Documentation names the step.
- Doctor strictness on missing answers could fail a project that updated scripts without answers; the doctor and answers change together through Copier update, and the failure message names the remedy.

## Verification

Render tests for GitHub-hosted (unchanged bytes), self-hosted single and multiple labels, and the repair step placement; Copier copy and update tests proving the answer persists across update; doctor unit tests for agreement, mismatch, missing answer, bad labels and GitLab; existing CI guardrail tests updated for the rendered `runs-on`; full platform checks.
