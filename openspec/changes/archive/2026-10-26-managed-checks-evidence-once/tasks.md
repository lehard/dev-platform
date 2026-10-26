## 1. One receipt

- [x] 1.1 Refuse an evidence-producing `select_checks --execute` before any command when the existing managed or quick evidence is reusable for the current task content, naming the evidence and reason.
- [x] 1.2 Portable `archive` reuses reusable `automated-checks.json` by the same rule and prints the decision; otherwise runs the checks as before.

## 2. Early stops

- [x] 2.1 Run the private-reference guard in `select_checks --execute` before any command.
- [x] 2.2 Stop before the full set when the affected-test precheck is unavailable, with a precheck-phase failure descriptor and failure evidence.

## 3. Verification

- [x] 3.1 Tests for the repeated-run refusal, archive reuse, guard and unavailable precheck; run selected checks and semantic verification.
