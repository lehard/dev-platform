## 1. Preflight current Project integration

- [x] 1.1 Confirm the supported authenticated GitHub Project API/CLI path and the stable locator for the existing user-level `Development Backlog` Project.
- [x] 1.2 Map the configured `Status` field/options and permission requirements without UI scraping.
- [x] 1.3 Reconcile this change with the active `adopt-gh-aw-process-automation` completion hook so both can compose on `finish_task`.

## 2. Add status reconciliation primitive

- [x] 2.1 Implement a self-contained, idempotent managed Project-status resolver/mutator using central Issue provenance and explicit Project configuration.
- [x] 2.2 Make already-correct transitions no-op and reject ambiguous/missing Project-item mappings.
- [x] 2.3 Add read/reconcile output that can distinguish desired/current state, permission/config blockers and post-merge reconciliation pending.

## 3. Integrate lifecycle transitions

- [x] 3.1 Reconcile `Ready -> In progress` in the standard managed start path before implementation continues.
- [x] 3.2 Reconcile active managed work to `In review` when its exact reviewable task PR is created/reused.
- [x] 3.3 Provide the supported `Blocked`/resume transition for genuine external blockers without treating ordinary CI wait as blocked.
- [x] 3.4 Reconcile terminal managed delivery to `Done` only after confirmed merge plus required lifecycle/source-task reconciliation.
- [x] 3.5 Ensure retries/resume repair stale Project status without changing authoritative Git/PR state or duplicating Project items.

## 4. Configuration and downstream delivery

- [x] 4.1 Extend validated Development Backlog configuration with the stable Project workflow locator required by status synchronization.
- [x] 4.2 Render/migrate the configuration and helper through Project Factory/Copier without overwriting project-owned content.
- [x] 4.3 Update canonical agent/workflow guidance to explain automatic status projection and the human-only `Backlog -> Ready` boundary.

## 5. Recovery and verification

- [x] 5.1 Add tests for start/In-progress, PR/In-review, blocker/resume, merged/Done, stale status retry, no-op idempotence and missing permissions/configuration.
- [x] 5.2 Add recovery tests for an already-started/merged managed task whose Project item is still `Ready`.
- [x] 5.3 Exercise at least one real Development Backlog transition chain against the configured Project without bypassing repository protection.
- [x] 5.4 Reconcile currently stale managed items only where source/delivery evidence is unambiguous and record the acceptance evidence.
- [x] 5.5 Run relevant unit/integration suites, template render/upgrade smoke, strict OpenSpec validation and semantic verification.
- [x] 5.6 Archive the verified change and publish it through the normal immutable release/managed rollout when platform/template runtime changes require a release.
