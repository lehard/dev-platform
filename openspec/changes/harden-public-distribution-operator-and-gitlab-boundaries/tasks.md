## 1. Public distribution candidate and sanitization

- [x] 1.1 Refactor public distribution so audit and snapshot consume the same deterministic candidate file set.
- [x] 1.2 Define/document the narrow allowed canonical product identity and prohibited operator/downstream reference policy for the fresh public snapshot.
- [x] 1.3 Audit the current snapshot candidate set, including archives/docs/tests/rollout surfaces, and replace personal downstream/backlog/bot references with synthetic/public-safe evidence or explicitly exclude non-product files.
- [x] 1.4 Add regression tests proving a prohibited owner/project reference in any packaged candidate blocks a green audit/snapshot.
- [x] 1.5 Ensure snapshot output is deterministic and records the exact source revision/candidate-set evidence used for cutover.

## 2. Bounded Git-history secret audit

- [x] 2.1 Add a bounded history-audit command that actually inspects supported reachable Git history/object scope for supported credential classes.
- [x] 2.2 Make its receipt state examined refs/range/object scope, pattern classes, findings, and limitations without printing secret values.
- [x] 2.3 Add synthetic-history tests for clean history and supported fake-secret findings.
- [x] 2.4 Update public-cutover documentation so current-tree audit and history-secret audit are distinct mandatory gates and neither is overstated.

## 3. Portable render versus operator guidance

- [x] 3.1 Identify every generated normative Development Backlog, Project-status, fleet and process-health instruction in the no-operator render.
- [x] 3.2 Refactor/split/conditionally render guidance so generic projects have a complete portable task/OpenSpec workflow with no mandatory operator action.
- [x] 3.3 Preserve operator managed-task/task-intake/process-health guidance behind explicit operator enablement without duplicating contradictory lifecycle rules.
- [x] 3.4 Add actual-render assertions for no-operator GitHub and GitLab projects and for an operator-enabled render.

## 4. Explicit operator isolation and coherent registry contract

- [x] 4.1 Change config loading so external operator env/path is ignored unless the project explicitly opts in to the operator layer.
- [x] 4.2 Define one documented precedence contract for operator config and rollout registry discovery; align `docs/operator-config.example.toml`, `managed_projects.py`, rollout code and tests.
- [x] 4.3 Remove or deprecate redundant implicit registry discovery that is not part of the documented operator contract.
- [x] 4.4 Add a bounded operator doctor/validation path for external TOML + registry schema/required fields with secret-safe diagnostics.
- [x] 4.5 Add tests proving global operator env cannot leak into a portable project and that explicit opt-in works.

## 5. Fail-closed exact-head GitLab completion

- [x] 5.1 Capture the exact validated/pushed task HEAD and verify the selected GitLab MR source branch, target branch and provider-reported head SHA against it.
- [x] 5.2 Resolve CI/pipeline evidence for that exact head and accept only the configured terminal green status.
- [x] 5.3 Treat pending/running as explicit resumable not-ready and failed/canceled/missing/unreadable/head-mismatch as non-success; do not emit generic completion.
- [x] 5.4 Make successful GitLab finish report `ready for human merge/acceptance` and perform no merge or production deployment.
- [x] 5.5 Expand GitLab tests for success, head mismatch, failed, pending/running, missing/unreadable pipeline, and no auto-merge.
- [x] 5.6 Run focused GitHub publication regressions to prove provider hardening does not weaken existing exact-head/check behavior.

## 6. Final proof and cutover readiness

- [x] 6.1 Render clean no-operator standard projects for both GitHub and GitLab and verify their guidance/configuration contracts.
- [x] 6.2 Run operator-enabled synthetic validation proving external config + registry works without public-tree state.
- [x] 6.3 Run current-tree public audit, bounded history-secret audit, deterministic snapshot dry-run, GitLab exact-head CI sandbox tests, OpenSpec verification and all required repository checks.
- [ ] 6.4 Record truthful verification evidence and archive only after all gates pass on the exact final revision.
- [ ] 6.5 Do not perform GitHub repository create/rename/visibility cutover, downstream migrations, or client production deployment from this task; leave those as explicit later owner/admin or repository-scoped actions.
