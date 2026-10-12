## 1. Copier question rules

- [x] 1.1 Make the `ci_runner_labels` validator in `copier.yml` enforce the doctor rule (blank, empty entry, duplicate, `[A-Za-z0-9._-]`, entries trimmed); put the shared rule in one documented place used by the doctor check.
- [x] 1.2 Ask `ci_runner` and `ci_runner_labels` only when `scm_provider` is `github`; confirm no answer is recorded for GitLab and rendering is unchanged.

## 2. Rollout preflight

- [x] 2.1 Add the runner preflight to `scripts/rollout_project.py`: applicability (target asks `ci_runner`, answers lack it, not GitLab), read committed `runs-on` for `platform-ci` and `provision`, classify default / simple labels / unsupported.
- [x] 2.2 For simple labels, prove each customized file equals its baseline render apart from the `runs-on` value; on proof, record the answers, restore only those `runs-on` lines, commit on the rollout branch before `copier update`.
- [x] 2.3 For anything unsupported or unproven, raise the rollout block naming repository, file, finding and next action before any update; keep the default-answers path unchanged for all-`ubuntu-latest` projects.

## 3. Documentation

- [x] 3.1 Rewrite the migration paragraph in `docs/managed-rollout.md` (automatic migration, stop conditions, action after a stop).

## 4. Tests

- [x] 4.1 Validator/doctor parity table test through the real Copier validator and `platform_doctor`; empty-entry and whitespace labels rejected at the question.
- [x] 4.2 GitLab render asks no runner question and records no runner answer.
- [x] 4.3 Rollout tests on a real Copier render of an earlier release with hand-edited `runs-on`: migrated in `harness_mode=platform` and `harness_mode=project` (answers, runner, repair step, no `.rej`, doctor green); unsupported cases stop with the named message and leave the default branch untouched; all-`ubuntu-latest` and older-target cases take the unchanged path.

## 5. Verification and delivery

- [ ] 5.1 Regenerate the platform manifest; run the required platform checks; truthful semantic verification; archive; retrospectives; publication. The change must be released before the tag that first contains `ci_runner`.
