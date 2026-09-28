## Routing source

Reuse `managed_task.authoring_config(root)`: it already validates `development_backlog.repository`, a `project:<slug>` label and a `P0..P3` default. The configured project label belongs to the checkout's own repository (`managed_task.origin_repository`). Neither the project config nor the operator config maps other repositories to labels, so a Requirement for another target must be created from that target's checkout (or through the ChatGPT adapter reading that target's config). Creating it from the wrong checkout would silently mislabel the card, so it is refused.

## Create sequence

1. Resolve config; normalize `--repository` and require equality with `development_backlog.repository`.
2. Normalize `--target-repository` and require equality with the origin repository.
3. Resolve priority (`--priority` or `default_priority`) through `managed_task.priority_label`.
4. `managed_task.validate_backlog_labels` proves the project and priority labels exist; `type:requirement` keeps its existing `ensure_label`.
5. `gh issue create` with all three labels.
6. Read back through `fetch_issue`. Conflicting `project:*`/`priority:*` labels fail with the Issue reference. Missing expected labels are added to that exact Issue once and re-read; the final check requires `type:requirement`, exactly the expected project label and exactly the expected priority label.

No duplicate search is added; creation semantics otherwise stay as today.

## ChatGPT adapter

The protocol's Requirement section gains: resolve `[development_backlog]` from the target repository's default branch `.dev-platform.toml`; stop when it is missing, invalid, or names another Backlog repository; apply `type:requirement` plus the configured project label and the explicit or default priority; verify exactly one of each in the read-back. Incubated Issues keep excluding both labels.
