# Promotion loop

Shared process improvements begin as local evidence, not automatic policy changes.

1. Record only high-signal friction locally with `agent_friction.py record`.
2. Review recurring/project-vs-platform candidates locally.
3. For a reusable platform candidate, run `agent_friction.py promote <id> --dry-run`.
4. If the sanitized payload is appropriate, run `agent_friction.py promote <id>` to create a central `dev-platform` GitHub Issue through authenticated `gh`.
5. Review evidence across projects. One event is not automatically a permanent rule.
6. If accepted, create an OpenSpec change in `dev-platform`.
7. Release the platform and propagate through reviewed Copier upgrade PRs.

Raw evidence is intentionally omitted from promotion because it may contain machine-local, customer, financial, operational or credential-adjacent context. Promotion includes only sanitized observation, hypothesis and proposed reusable change.
