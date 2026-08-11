## 1. Lock the transport and provenance contract

- [x] 1.1 Add the `managed-openspec:v1` package parser/validator contract with exactly one supported package, JSON manifest fields, explicit artifact delimiters, containment-safe relative paths, and stable package revision calculation.
- [x] 1.2 Define normalized GitHub issue references and target-repository identity checks for standard GitHub HTTPS/SSH `origin` forms.
- [x] 1.3 Define provenance persisted beside an imported change and the idempotency/conflict rules for unchanged package retry, changed package retry, and unrelated same-name changes.
- [x] 1.4 Add focused unit fixtures for valid package, missing/duplicate package, unsupported version, incomplete manifest, unsafe path, wrong target, and package revision stability.

**Commit boundary:** transport/provenance parser and tests can land independently before OpenSpec materialization.

## 2. Implement deterministic managed-task import

- [x] 2.1 Add the reusable template helper (`template/scripts/managed_task.py`, plus only the minimal source-repository wrapper needed for dev-platform dogfooding) using existing platform root/GitHub-auth helpers and structured GitHub output.
- [x] 2.2 Fetch the referenced issue/comments from a private backlog without introducing a new secret; fail before mutation when auth/read access is unavailable.
- [x] 2.3 Resolve current target repository identity and current synchronized/fetched target commit used for freshness reporting; reject target mismatch.
- [x] 2.4 Use the installed OpenSpec CLI/current schema to create or inspect the intended change before writing package artifacts. Do not hand-create a schema that the current CLI rejects.
- [x] 2.5 Validate the entire package before writes, materialize only permitted planning artifacts, persist provenance, and run the repository-supported structural OpenSpec preflight.
- [x] 2.6 Ensure successful import exits before apply/implementation and clearly reports `fresh` versus `stale-needs-semantic-preflight` state.
- [x] 2.7 Make identical re-import safe and make changed-package or unrelated same-name conflicts fail closed without overwriting repository-local OpenSpec.

**Commit boundary:** importer + unit/integration tests, without agent-guidance changes.

## 3. Add managed/quick agent contract

- [x] 3.1 Update root `AGENTS.md` for dev-platform bootstrap/dogfooding: a supplied Development Backlog issue is a managed task; after materialization local OpenSpec is canonical and the issue is not a second implementation backlog.
- [x] 3.2 Update `template/AGENTS.md.jinja` with the universal managed path, quick path, semantic preflight rule, and quick → managed escalation boundary without changing profile-specific branch/worktree behavior.
- [x] 3.3 Update generated engineering workflow documentation with the human command shape (`take owner/repo#N`), import/preflight boundary, and the fact that v1 does not dispatch automatically or mutate GitHub Project status.
- [x] 3.4 Ensure guidance does not tell agents to recreate a backlog/OpenSpec for small scoped quick fixes.

**Commit boundary:** guidance/documentation after the importer interface is fixed.

## 4. Integrate with the project factory safely

- [x] 4.1 Add the new helper to required template contract checks and, if platform doctor owns the common-file inventory, to the appropriate common required-file set.
- [x] 4.2 Render all supported workflow profiles and verify the importer/guidance are present without altering `light`, `standard`, or `multi-agent` start/finish semantics.
- [x] 4.3 Extend Copier upgrade smoke so an existing managed repository can receive the new file/guidance through reviewed update behavior and path collisions remain reviewable rather than silently overwritten.
- [x] 4.4 Confirm `harness_mode=project` repositories can use planning intake without the importer assuming platform ownership of their worktree/merge/check lifecycle.

**Commit boundary:** template/factory integration and upgrade tests.

## 5. Verify interaction boundaries and bootstrap path

- [x] 5.1 Add tests proving the importer never invokes apply, `start_task.py`, GitHub Project mutation, merge/publication, or gh-aw workflows.
- [x] 5.2 Add a stale-preparation test where `prepared_against` differs from current target state and import reports semantic-preflight-required rather than silently rejecting or blindly applying.
- [x] 5.3 Confirm the active `adopt-gh-aw-process-automation` and `durable-publication-recovery` changes are not semantically overwritten; resolve any implementation file overlap before parallel work.
- [x] 5.4 Document the one-time bootstrap for `lehard/development-backlog#1`: manually scaffold/import this package because the importer does not yet exist, then use the standard importer for subsequent managed tasks.

## 6. Platform validation and completion

- [x] 6.1 Run `python3 -m compileall -q template/scripts scripts`.
- [x] 6.2 Run `python3 scripts/managed_projects.py validate`.
- [x] 6.3 Run `python3 -m unittest discover -s tests -v`, including new importer/template/upgrade coverage.
- [x] 6.4 Render representative downstream projects and run the relevant generated doctor/OpenSpec structural checks.
- [x] 6.5 Perform semantic OpenSpec verification, resolve material findings, and record `OpenSpec-Verify: PASS` plus truthful `Verification-Method` in `verification.md`.
- [x] 6.6 Archive through `python3 template/scripts/openspec_lifecycle.py archive add-managed-backlog-intake`, commit the synchronized spec/archive result, and publish through the existing protected-main lifecycle.

**Final commit boundary:** verification/archive/spec synchronization only after implementation and platform checks pass.
