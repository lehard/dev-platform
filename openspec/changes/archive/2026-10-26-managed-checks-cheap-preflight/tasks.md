## 1. Preflight

- [x] 1.1 Refuse managed `select_checks --execute` without `--evidence` before any command, naming the evidence path.
- [x] 1.2 Refuse managed `select_checks --execute` when `archive_content_problems` reports the change, naming the problems.
- [x] 1.3 Run the manifest check before `run_test_groups.py --all` in `dev-platform/checks.toml`.

## 2. Verification

- [x] 2.1 Tests for both refusals (no command started) and the archive-ready pass; run selected checks and semantic verification.
