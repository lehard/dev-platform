## 1. Remove the workflow

- [x] 1.1 Delete `.github/workflows/process-issue-triage.md` and `.github/workflows/process-issue-triage.lock.yml`.
- [x] 1.2 Remove triage from `WORKFLOWS` and the lock drift list in `scripts/validate_agentic_workflows.py`; recompile the remaining workflows with the pinned gh-aw and commit any `.github/aw` metadata change.
- [x] 1.3 Remove triage from `CLOUD_MAINTENANCE_WORKFLOWS` in `scripts/cloud_maintenance_preflight.py`.

## 2. Tests

- [x] 2.1 `tests/test_agentic_workflows.py`: drop triage-specific source/lock assertions; add a test that the triage source and lock are absent and no agentic source triggers on `issues:`.
- [x] 2.2 `tests/test_ci_guardrails.py` and `tests/test_cloud_maintenance_preflight.py`: drop triage from the workflow lists/fixtures.

## 3. Documentation

- [x] 3.1 `docs/agentic-workflows.md`: installed-workflow list and operations examples no longer describe triage; state it is disabled by owner decision and friction goes to the Process Health Review.
- [x] 3.2 `docs/engineering/agent-workflow.md` and `template/docs/engineering/agent-workflow.md.jinja`: replace "cloud triage/review" with the periodic Process Health Review.

## 4. Verification and delivery

- [x] 4.1 Regenerate the platform manifest; required platform checks; truthful semantic verification; archive; retrospectives; publication.
