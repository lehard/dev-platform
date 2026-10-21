## 1. Generated-file declaration
- [x] 1.1 Add a declaration reader in `_platform_common.py` that reads `[[generated_files]]` from the check configuration at a given commit; explicit errors for malformed or duplicate entries and a missing `paths.checks` file.
- [x] 1.2 Declare `template/dev-platform/platform-manifest.json` in `dev-platform/checks.toml`; add `--root` to `scripts/generate_platform_manifest.py`.

## 2. Behind-mergeable contract
- [x] 2.1 Replace behind-disjoint classification with behind-mergeable (clean merge, or conflicts only in generated files declared at the observed main); record overlapping paths and generated conflicts.
- [x] 2.2 Use it in `select_checks.py` evidence, `project_publish.py` handoff push, `finish_task.py` status/re-admission and `task_reconciliation.py`; non-coordinator tasks keep the fresh-base gate.
- [x] 2.3 Update `docs/engineering/agent-workflow.md`.

## 3. Verification
- [x] 3.1 Regression tests: manifest-only conflict passes; clean overlap of an ordinary file passes; real conflict blocks naming files and the reconcile command; a declaration added only by the candidate does not apply; malformed declaration fails; non-coordinator task stays blocked.
- [ ] 3.2 Run full validation and semantic OpenSpec verification.
