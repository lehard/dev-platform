## 1. Inventory and public/operator boundary

- [x] 1.1 Inventory source/template/docs/scripts/config for owner-specific repository names, backlog/project/bot defaults, live managed-project inventory and GitHub-only lifecycle assumptions.
- [x] 1.2 Classify each relevant surface as public core, provider adapter, project-owned or operator-owned; record the resulting ownership map.
- [x] 1.3 Add a bounded current-tree/history audit for prohibited live operator state and actual credential/secret patterns, with explicit distinction between product-cleanup findings and security incidents.
- [x] 1.4 Define the supported external operator configuration contract and precedence without making it required for ordinary project work.

## 2. Generic Project Factory and configuration split

- [x] 2.1 Remove `lehard/development-backlog`, owner/Project-number, source bot identity, promotion target and comparable installation-specific values as unconditional Copier defaults.
- [x] 2.2 Make Development Backlog/fleet/process-health/operator instructions and generated surfaces explicit opt-ins.
- [x] 2.3 Move live managed-project inventory out of generic public distribution state; preserve generic fleet code only against external registry/config plus synthetic test fixtures.
- [x] 2.4 Ensure a default `standard` render can initialize OpenSpec and run readiness/checks without operator configuration.
- [x] 2.5 Add regression coverage proving clean default render contains no prohibited owner-specific state.

## 3. Provider-neutral standard delivery and minimal GitLab adapter

- [x] 3.1 Define/refactor the standard publication contract around provider-neutral branch/change/check/terminal-state semantics without weakening current GitHub exact-head/check safety.
- [x] 3.2 Keep GitHub-specific PR/CLI/Actions behavior behind the GitHub adapter boundary.
- [x] 3.3 Add the bounded GitLab adapter required by the client pilot: branch push, MR create/reuse for exact task identity, CI-status observation and human merge/acceptance stop.
- [x] 3.4 Add thin GitLab CI orchestration that invokes the same repository-owned verification entrypoints used locally.
- [x] 3.5 Cover GitHub regression and GitLab sandbox behavior with focused tests.

## 4. Clean public snapshot and history strategy

- [x] 4.1 Implement/document deterministic sanitized-snapshot preparation from a verified source tree.
- [x] 4.2 Block snapshot readiness on prohibited live operator state and unresolved real-secret findings.
- [x] 4.3 Document the default fresh-history cutover: no destructive rewrite solely for non-sensitive project/operator references.
- [x] 4.4 Produce a concrete admin cutover checklist covering temporary/new repository identity, canonical-name handoff, old repository private/archive decision and consumer migration.
- [x] 4.5 Keep actual GitHub repository create/rename/visibility mutations as an explicit owner/admin gate unless repository-admin automation is deliberately added later.

## 5. Client-like sandbox proof

- [x] 5.1 Render a clean greenfield standard project using GitLab delivery with no operator integrations.
- [x] 5.2 Configure minimal synthetic application/check commands sufficient to exercise the lifecycle without coupling Dev Platform to a specific application framework.
- [x] 5.3 Run a representative OpenSpec -> decomposition/implementation -> code/tests -> repository-owned checks -> GitLab-style CI/MR -> human acceptance dry-run.
- [x] 5.4 Confirm generated repo/docs contain no owner-specific fleet/backlog defaults and no hidden dependency on the old source installation.
- [x] 5.5 Record gaps found by the dry-run and fix only those required for the bounded external-client MVP.

## 6. Documentation, verification and release preparation

- [x] 6.1 Update README/ownership/adoption docs to explain public core, provider adapters, project-owned configuration and external operator layer.
- [x] 6.2 Document what is intentionally deferred: full GitLab fleet/backlog parity, production deploy automation and downstream repository migration.
- [x] 6.3 Run Project Factory, platform-config, standard lifecycle, GitHub regression, GitLab sandbox, OpenSpec and sanitization checks required by the repository.
- [x] 6.4 Record truthful verification evidence and prepare the immutable platform release/sanitized snapshot that can be used at the owner-admin cutover gate.
- [x] 6.5 Do not migrate personal downstream repositories from this task; create/reuse repository-scoped tasks after the public release/cutover contract is ready.
