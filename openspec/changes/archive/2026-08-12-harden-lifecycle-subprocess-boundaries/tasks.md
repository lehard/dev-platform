## 1. Preflight

- [x] 1.1 Audit current validation subprocess environment flow and enumerate repository-binding Git variables relevant to the observed `#152` failure.
- [x] 1.2 Audit checked and `check=False` `run_git` call sites, including any code that catches `CalledProcessError` or maps Git failures to resumable lifecycle states.
- [x] 1.3 Build focused regression fixtures for a nested temporary repository and for a checked Git failure with sensitive-looking diagnostic content.

## 2. Validation environment isolation

- [x] 2.1 Add a bounded environment sanitizer/scoping mechanism for platform-owned validation/check subprocesses.
- [x] 2.2 Ensure repository-specific overrides are removed by default while ordinary tool/runtime environment remains intact.
- [x] 2.3 Keep any required Git override local to the exact Git operation that needs it.

## 3. Git diagnostics

- [x] 3.1 Add a bounded actionable error representation for checked Git failures with command, cwd, exit code and sanitized useful output.
- [x] 3.2 Preserve non-raising `check=False` behavior and existing higher-level resumable state classification.
- [x] 3.3 Add/redesign only the minimum redaction needed so credentials and unbounded output are not exposed.

## 4. Regression coverage

- [x] 4.1 Reproduce and prevent the temporary-repository contamination class from `dev-platform#152`.
- [x] 4.2 Reproduce and improve the operator-facing failure class from `dev-platform#153`.
- [x] 4.3 Cover normal validation environment, scoped override, checked failure, `check=False`, redaction and higher-level blocker behavior.

## 5. Verification and delivery

- [x] 5.1 Run relevant lifecycle/check tests and the complete required platform validation selected by the current contract.
- [x] 5.2 Perform semantic OpenSpec verification and record truthful evidence.
- [x] 5.3 Archive the change through the normal OpenSpec lifecycle.
- [x] 5.4 If runtime/template code changes, publish through the ordinary immutable platform release and managed rollout; no implementation of backlog #18 or #19 is implied by this task.
