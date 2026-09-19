## 1. Remove concrete operator backlog identity from public product evidence

- [x] 1.1 Inventory every current-candidate reference to the maintainer's Development Backlog repository and classify it as product identity, operator configuration, test fixture, accepted spec evidence, or historical excluded evidence.
- [x] 1.2 Remove the concrete Development Backlog repository from the public canonical-identity allowlist.
- [x] 1.3 Replace current-candidate test/spec/example references with synthetic operator identities while preserving Development Backlog capability semantics.
- [x] 1.4 Add regression coverage proving generic and operator-enabled fixtures do not require the maintainer's concrete backlog repository.

## 2. Externalize one-shot private cutover deny data

- [x] 2.1 Define the smallest versioned external cutover-policy schema for additional prohibited repositories/compatibility markers needed only during migration.
- [x] 2.2 Add explicit audit/snapshot CLI/config input for that policy; missing/malformed explicitly requested policy fails closed.
- [x] 2.3 Remove private downstream project names and split-literal reconstructions from shipped sanitizer source.
- [x] 2.4 Ensure policy values are not copied into candidate files, tar snapshot, generated docs, or receipts; record only bounded non-sensitive provenance/digest.
- [x] 2.5 Add focused tests for valid/missing/malformed policy, detection, redacted receipt, and absence of policy/private marker material from snapshot.

## 3. Preserve reusable public sanitization and source completeness

- [x] 3.1 Keep one deterministic candidate set shared by audit and snapshot.
- [x] 3.2 Preserve #122 inclusion of tests, accepted OpenSpec specs, CI, eval fixtures, and extracted-snapshot completeness smoke.
- [x] 3.3 Verify reusable audit remains useful without the old operator cutover policy and does not depend on the maintainer's external backlog/fleet state.
- [x] 3.4 Add a final candidate search/assertion that only approved canonical source identity and synthetic/example operator identities remain.

## 4. Produce operator handoff without committing private state

- [x] 4.1 Document the exact external operator fields required by the current installation before the next real managed rollout: Development Backlog config, `rollout.registry_path`, rollout identity if required, and any still-live `rollout.legacy_harness_migrations` values.
- [x] 4.2 Identify which values can be derived from existing operator/repository evidence and which require owner input; do not guess or commit unknown real values.
- [x] 4.3 Provide/verify the supported operator doctor/validation sequence and fail-closed behavior when required state is absent.
- [x] 4.4 Keep the handoff generic/public-safe; real operator TOML and registry remain outside repository source.

## 5. Final cutover evidence

- [x] 5.1 Run current-tree audit with the external one-shot cutover policy on the exact final revision.
- [x] 5.2 Run reusable public audit without private deny data and bounded history-secret audit on that same revision.
- [x] 5.3 Generate/extract the deterministic snapshot and run source-completeness smoke plus full required checks, OpenSpec validation, operator isolation, rollout, and GitLab regressions from the appropriate source/snapshot environments.
- [x] 5.4 Record exact revision, candidate/snapshot digest, policy provenance digest, and truthful verification evidence.
- [x] 5.5 Do not perform GitHub repository create/rename/visibility cutover or downstream migrations in this task; stop at a verified admin-ready snapshot and operator handoff.
