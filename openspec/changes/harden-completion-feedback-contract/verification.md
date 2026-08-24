# Verification: Harden completion feedback contract

OpenSpec-Verify: PASS
Verification-Method: Manual equivalent semantic OpenSpec review of the authored outcome, success evidence, completeness, correctness, and coherence against the implementation and regression suite; `/opsx:verify` is not available in this environment.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- **Completeness: PASS.** The central and rendered OpenSpec workflows now carry the same platform-owned receipt marker, and regression coverage checks both documents. Archive preflight names the exact missing marker, canonical workflow location, and repair before selected checks or evidence mutation.
- **Correctness: PASS.** The retrospective reads only existing current-branch, high-severity `lifecycle-*` records from the friction log. It stores bounded dispositions inside the existing checkpoint record, rejects unclassified candidates both when recording and when finishing, and does not create a second lifecycle event or state store.
- **Coherence: PASS.** `--event` is the `new-recorded` path; `resolved-in-task` and `already-recorded` use a concise disposition only when a lifecycle failure exists. Clean tasks retain `checkpoint --result none` without additional arguments.

## Automated evidence run before archive

- `python3 -m unittest tests.test_friction_review tests.test_openspec_lifecycle tests.test_template_contract` — PASS (81 tests).
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `openspec validate harden-completion-feedback-contract --strict --no-interactive` — PASS.
- `python3 scripts/run_test_groups.py --all` — PASS (13 groups; 733 declared/discovered tests).

The archive helper generates `automated-checks.json` from its own selected-check invocation and validates that evidence before archive mutation completes.
