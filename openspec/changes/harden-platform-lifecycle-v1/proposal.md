# Proposal: harden platform lifecycle v1

## Why

The initial Project Factory centralizes the workflow, but five gaps prevent safe broad rollout: task branches can start from stale local main, completed work still needs manual GitHub hand-off, OpenSpec drift/verify are not explicit platform contracts, every project inherits multi-agent machinery, and downstream reusable CI follows mutable `@main`.

## Goals

- make start/finish GitHub-aware and zero-hand-off while preserving safe aborts on divergence;
- enforce a no-silent-divergence OpenSpec contract and require semantic verify for non-trivial changes;
- introduce composable `light`, `standard`, and `multi-agent` workflow profiles;
- pin downstream reusable CI to a versioned release ref instead of `main`;
- add OpenSpec CLI compatibility policy and deliberate sanitized friction promotion to a central inbox.

## Non-goals

- do not adopt or modify `Jara_Fin` while its current agents are active;
- do not auto-merge GitHub PRs;
- do not force-push, auto-resolve Git divergence, or silently upgrade global OpenSpec installations;
- do not vendor OpenSpec-generated skills.

## Affected surfaces

`copier.yml`, generated `.dev-platform.toml`, root agent contract, Git lifecycle scripts, OpenSpec workflow docs/config, friction tooling, downstream CI reference, template validation and smoke tests.
