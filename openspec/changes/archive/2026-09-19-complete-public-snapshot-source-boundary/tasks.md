## 1. Re-establish the canonical-source snapshot boundary

- [x] 1.1 Inventory every packaged README, CI, release, OpenSpec, and verification reference that requires a repository-owned path.
- [x] 1.2 Replace the broad `tests` / `openspec` exclusions with a narrow documented source-distribution policy that retains required tests, OpenSpec configuration, and accepted `openspec/specs/`.
- [x] 1.3 Decide and document the minimal historical/maintenance exclusions, including whether `openspec/changes/archive/` is excluded while current accepted specs remain.
- [x] 1.4 Add regression tests proving packaged CI/README cannot reference a path omitted by the public snapshot.

## 2. Add extracted-snapshot source completeness proof

- [x] 2.1 Add a deterministic snapshot-smoke path that extracts the generated tar into a clean temporary directory.
- [x] 2.2 From the extracted snapshot, validate required internal docs/README paths and every repository-owned CI entrypoint used by the packaged workflows.
- [x] 2.3 Run the bounded public-source verification/test/spec checks that make the fresh repository developable from its first commit.
- [x] 2.4 Record exact source revision and snapshot digest in the smoke/cutover evidence.

## 3. Remove private-project compatibility from public rollout code

- [x] 3.1 Inventory Jara/Planner/Cuby-specific constants, hashes, messages, functions, override source payloads, branches, tests, and docs that are part of the public candidate.
- [x] 3.2 Determine for each live shim whether it is obsolete, needs a one-time downstream migration, or requires an ongoing external operator-owned compatibility override.
- [x] 3.3 Refactor the public rollout core to generic migration/rollout primitives only; remove private project names and production-specific compatibility payloads from packaged source.
- [x] 3.4 Preserve necessary operator continuity through the smallest explicit external/operator or downstream transition, without committing live private compatibility state into the public repository.
- [x] 3.5 Replace private regression examples with synthetic fixtures while preserving the generic invariants those tests protect.

## 4. Harden sanitization for compatibility leakage

- [x] 4.1 Extend public-distribution policy/checks with bounded project-specific compatibility markers beyond `owner/repo` matching.
- [x] 4.2 Add tests proving a packaged Jara/Planner/Cuby-style live shim blocks audit/snapshot even without an owner-qualified repository string.
- [x] 4.3 Keep canonical `lehard/dev-platform` identity and synthetic examples explicitly distinguishable from prohibited operator compatibility.

## 5. Final verification

- [x] 5.1 Generate the final candidate snapshot and run current-tree audit plus the existing bounded history-secret audit.
- [x] 5.2 Extract the snapshot and run the new source-completeness smoke, link/path checks, accepted OpenSpec validation, and required public test/CI entrypoints from inside it.
- [x] 5.3 Run full repository checks and focused rollout, operator isolation, GitLab exact-head, and public-distribution regressions on the exact final revision.
- [x] 5.4 Record truthful verification evidence and archive only after all gates pass.
- [x] 5.5 Do not perform repository-admin cutover or downstream migrations from this task; report any required operator/downstream transition explicitly for the next controlled action.
