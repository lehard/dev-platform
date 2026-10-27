## 1. CI Python check
- [x] 1.1 Add `scripts/check_ci_python.py`: read the CI version from the workflow job's `setup-python` step, compare with the running interpreter, compile with the CI-version interpreter on mismatch, refuse explicitly naming both versions.
- [x] 1.2 Add the check to the full and Python command sets in `dev-platform/checks.toml`.

## 2. Verification
- [x] 2.1 Tests: match passes; mismatch compiles and fails on a CI-only compile error; missing interpreter, wrong interpreter version and unreadable workflow are refused naming both versions.
- [x] 2.2 Run full validation and semantic OpenSpec verification.
