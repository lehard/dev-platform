# Design: Public core, external operator layer, provider adapters

## Context

The current source repository is simultaneously the product source and the owner's active control plane. That was useful during dogfooding, but it leaks installation-specific defaults into Project Factory and makes an external user inherit assumptions about the owner's backlog, fleet and GitHub account.

A client pilot creates a second pressure: the client uses GitLab and should receive a minimal, reproducible agent-ready project, not a forked private copy of Dev Platform.

The public repository is already public, so old non-sensitive references cannot be made meaningfully "never exposed" by deleting them from `main`. Rewriting current history would also invalidate commit identities/tags and complicate immutable-release/Copier consumers. The clean product identity should therefore be established from a sanitized snapshot with fresh history, while actual secrets follow a separate security-remediation path.

## Decisions

1. **One product core.** Keep one canonical Dev Platform codebase and Project Factory. Do not create a long-lived `client-starter` fork.
2. **Four ownership layers.**
   - public core: reusable lifecycle, OpenSpec, verification, routing, isolation and Project Factory;
   - provider adapters: GitHub and bounded GitLab delivery implementations;
   - project-owned config: stack/domain/check/deploy details of one generated repository;
   - operator-owned config: fleet inventory, shared backlog, account/bot identity and cross-repository rollout policy.
3. **Operator is opt-in.** A project must work without the operator layer. Operator capabilities load external configuration explicitly and fail only when the operator-specific action itself is invoked.
4. **No owner defaults in generic render.** Source-owner repository names, bot login and GitHub Project identity are not default Copier answers.
5. **Provider-neutral standard lifecycle.** Core lifecycle owns branch/change/check/terminal-state semantics; adapters own GitHub PR or GitLab MR/API details.
6. **Bounded GitLab scope.** First implementation covers standard task branch publication, MR create/reuse, CI status observation and human merge/acceptance. Central GitLab fleet rollout/backlog parity is deferred.
7. **Fresh public history.** Prepare a deterministic sanitized source snapshot, validate it, then use it as the root of the canonical public history. Keep old source available during migration; owner performs repository admin/rename/visibility operations at the cutover gate.
8. **Secrets are different from references.** A bounded secret/history audit precedes cutover. A real leaked secret is rotated/revoked first and may require dedicated history cleanup; ordinary project names do not.
9. **Downstream migrations are separate.** This change may publish a migration contract/release but does not silently mutate every personal repository.
10. **Client proof before cutover.** A client-like sandbox must prove clean render and the OpenSpec -> code/tests -> checks -> QA/acceptance path before the new public source is declared canonical.

## Migration sequence

1. Inventory current public/template/operator coupling and classify each surface as public core, provider adapter, project-owned or operator-owned.
2. Introduce external/optional operator configuration and remove owner-specific generic defaults.
3. Make generated instructions/docs conditional on enabled operator capabilities.
4. Extract provider-neutral publication semantics and add bounded GitLab standard adapter.
5. Build sanitization/history audit and deterministic public snapshot validation.
6. Render a clean client-like sandbox and execute the basic workflow.
7. Produce the cutover checklist and verified snapshot/release.
8. Owner performs GitHub repository-admin cutover.
9. Migrate downstream personal projects through separate repository-scoped tasks.

## Safety

- Do not auto-delete or rewrite current public history during implementation.
- Do not copy credentials, private project payloads or live operator inventory into test fixtures.
- Do not weaken current GitHub publication safety while extracting the adapter boundary.
- Do not make GitLab support conditional on a hidden second template.
- Do not mutate client production or downstream personal repositories from this target-repository change.
