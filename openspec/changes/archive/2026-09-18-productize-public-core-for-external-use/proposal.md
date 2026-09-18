# Proposal: Productize public Dev Platform core for external use

## Why

Dev Platform is about to be used outside the owner's own repository fleet: it is being prepared for public promotion and for a client pilot that uses GitLab and a greenfield product. The current public source still mixes reusable platform behavior with one operator installation: concrete managed repositories, Development Backlog defaults, GitHub Project ownership, bot identity, promotion targets and GitHub-first publication semantics.

Removing those values only from current `main` would clean the working tree but not create a clean product history. At the same time, forking a second long-lived starter would create two drifting platforms.

The platform needs an explicit product boundary: a generic public core that renders clean projects, optional provider adapters, and an external operator layer for owner-specific fleet/backlog configuration.

## What Changes

- Separate portable project/platform configuration from operator-specific inventory, backlog, bot and fleet configuration.
- Make owner-specific integrations opt-in rather than default output of Project Factory.
- Keep one canonical Project Factory instead of introducing a separate client-starter fork.
- Define a provider-neutral standard publication contract with GitHub and a bounded GitLab adapter sufficient for the first client pilot.
- Add a public-distribution invariant and a deterministic sanitized-snapshot path for establishing a clean canonical public repository history.
- Treat real credentials/secrets found by history audit as a security incident requiring rotation/revocation and bounded removal; ordinary project names do not trigger destructive history rewrite.
- Add a client-like sandbox proving clean bootstrap and the basic OpenSpec -> implementation -> verification path before public/admin cutover.

## Capabilities

### Modified Capabilities

- `project-factory`: generic renders become independent of one operator's backlog/fleet/GitHub installation and can select an SCM/delivery adapter.
- `platform-config`: project-portable configuration is separated from operator-specific external configuration.
- `standard-profile-lifecycle`: publication semantics become provider-neutral at the core boundary, with bounded GitLab support alongside GitHub.

### Added Capabilities

- `public-distribution`: public source/release candidates are sanitized from operator-specific state and can be cut over from a verified snapshot without rewriting non-sensitive old history.

## Impact

- Copier questions and generated configuration/instructions.
- Platform/operator ownership documentation and validation.
- Publication adapter boundaries and standard-profile tests.
- Minimal GitLab MR/CI-status integration for the client sandbox.
- Public repository cutover tooling/runbook and history/secret audit.
- No automatic migration of downstream personal repositories and no production deployment to the client.
