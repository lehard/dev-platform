## 1. Trace

- [x] 1.1 `delivery_trace.py` with `enabled`, `valid`, `ensure` and the `check` entrypoint, and its `scripts/` adapter.
- [x] 1.2 `publish_pr` traces the head before it reads the expected head.
- [x] 1.3 `reconcile` keeps the trace of a traced published head.
- [x] 1.4 `delivery_trace = true` in `dev-platform/checks.toml`.

## 2. Guard

- [x] 2.1 Early `validate` step in `.github/workflows/ci.yml` reading the PR head SHA.

## 3. Contract and verification

- [x] 3.1 Decision record and documentation, including the way out of a refusing guard.
- [x] 3.2 Tests for the trace, the guard, publication, reconcile, unchanged content gates and a project without the setting.
- [ ] 3.3 Selected checks, strict `openspec validate`, semantic verification and live proofs on real PRs.
