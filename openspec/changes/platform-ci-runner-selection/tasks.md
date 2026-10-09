## 1. Template answers and rendering

- [x] 1.1 Add `ci_runner` and `ci_runner_labels` questions with validator to `copier.yml`.
- [x] 1.2 Render `runs-on` and the self-hosted shared-workspace repair step in `dev-platform.yml.jinja`; render `runs-on` and portable `curl` provisioning in `process-health-labels.yml.jinja`.

## 2. Doctor agreement

- [x] 2.1 Add the doctor check that committed workflow runner and repair step agree with recorded answers and that labels are well formed; keep central and template copies identical.

## 3. Documentation and evidence

- [x] 3.1 Document the answers and the migration for projects that hand-edited their runner.
- [x] 3.2 Add render, Copier update and doctor regression tests; update CI guardrail tests.
- [x] 3.3 Run required platform checks, record truthful verification, archive, retrospectives and publication.
