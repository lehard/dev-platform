## 1. Baseline and diagnostics

- [x] 1.1 Inventory the current local and CI validation path, establish reproducible isolated and contended baselines, and record command-level timing evidence.
- [x] 1.2 Add concise successful output plus failure-safe diagnostics (command, status, bounded output/artifact reference) without hiding failures.
- [x] 1.3 Add regression tests for duration recording and diagnostic behavior.

## 2. Safe selection policy

- [x] 2.1 Specify and implement distinct `local affected` and `protected full` selection modes.
- [x] 2.2 Maintain a tested explicit path-to-check map; make unknown/ambiguous/high-impact paths select the full suite.
- [x] 2.3 Add contract tests proving local selected success cannot satisfy protected PR merge authority.

## 3. Evidence-gated parallelism

- [x] 3.1 Audit candidate test/check partitions for mutable shared resources and encode required isolation or serialization.
- [x] 3.2 If benchmarks and isolation audit support it, implement safe partitions with a stable aggregate required CI check; otherwise document the decision and retain sequential full validation.
- [x] 3.3 Benchmark before/after in isolated and contended contexts; document measured effect, operational cost, and residual risk.

## 4. Verification and delivery

- [x] 4.1 Run targeted selector/runner tests, full platform tests, compile checks, managed-project validation, lifecycle check, and relevant Copier smoke checks.
- [x] 4.2 Perform semantic OpenSpec verification, record the actual receipt, archive only after all acceptance criteria pass, then publish through the protected-main lifecycle.
