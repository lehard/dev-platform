## 1. Reuse decision

- [x] 1.1 Add `automated_evidence_reuse` to `template/scripts/openspec_lifecycle.py`: version-2 fields, exact base equality and remote-main ancestry, recomputed `select_checks.py --json` selection covered by successful executed commands; named reasons; errors raise
- [x] 1.2 Call it from `template/scripts/finish_task.py` on the `portable` managed delivery path only, after the completion preflight and before `run_checks`; print `DEV_PLATFORM_CHECK_REUSE` and the stage marker; leave coordinator, GitLab, non-managed and queue-merged paths unchanged

## 2. Documentation

- [x] 2.1 Document the reuse line and the conditions that force validation in the agent workflow guide

## 3. Verification and delivery

- [x] 3.1 Unit tests: reuse on unchanged archived content; refusal for changed code/test content, changed base after reconcile, a changed `checks.toml` selection, a missing or failed required command, version-1 evidence, substituted evidence of another checkout; coordinator and non-managed paths still run checks
- [x] 3.2 Integration test in a rendered `portable` project: count `select_checks.py --execute` invocations over `archive -> finish` (2 before, 1 after) for unchanged content, 2 after a reconcile that changes the base, and a named stop with no extra execution after a code change between archive and finish; check Copier update of an existing render
- [x] 3.3 Run the selected checks and full validation, record semantic verification with the before/after execution counts (no time-saving claim), archive and publish
