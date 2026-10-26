## 1. Board
- [x] 1.1 Exclude paths declared generated at the observed `origin/<main>` from hard conflicts in `agent_board._admission_conflicts`; keep them in the soft warning; fail the scope gate on an unobserved main or a malformed declaration.
- [x] 1.2 Update the board/scope-gate paragraph of `docs/engineering/agent-workflow.md`.

## 2. Verification
- [x] 2.1 Regression tests: two active tasks sharing only the declared generated manifest get no hard overlap and a soft warning; a shared undeclared file stays hard; a declaration added only on the task branch does not soften; a malformed declaration stops the gate.
- [x] 2.2 Run full validation and semantic OpenSpec verification.
