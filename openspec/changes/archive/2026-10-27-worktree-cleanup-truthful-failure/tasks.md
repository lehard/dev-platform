## 1. Truthful cleanup result
- [x] 1.1 `_cleanup_target`: status `failed` when errors were recorded.
- [x] 1.2 `main`: exit 1 for a cleanup payload with errors or status `refused`/`failed`, targeted or `--all`.

## 2. Verification
- [x] 2.1 Tests: targeted cleanup with an error is `failed` and exits 1; `--all --apply` with an error exits 1; a refused `--all` preview exits 1; successful and already-cleaned cleanups exit 0.
- [x] 2.2 Run full validation and semantic OpenSpec verification.
