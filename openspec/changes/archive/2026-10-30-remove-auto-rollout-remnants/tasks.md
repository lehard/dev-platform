## 1. Remove remnants
- [x] 1.1 Run the stale-rollout supersession step of `reconcile-stale-rollouts.yml` only on `workflow_dispatch`.
- [x] 1.2 Remove the legacy-harness migration and operator continuity from `scripts/rollout_project.py`; keep the conformance gate; update tests.
- [x] 1.3 Remove `[rollout.legacy_harness_migrations]` from `docs/operator-config.example.toml`, `docs/public-cutover.md`, `docs/managed-rollout.md`; describe the manual targeted rollout in `docs/managed-rollout.md`.

## 2. Verification
- [x] 2.1 Regenerate the manifest; full validation and semantic OpenSpec verification; record the registry evidence.
