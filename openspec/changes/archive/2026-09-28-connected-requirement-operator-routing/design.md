## Authority

The authoritative routing values stay `[development_backlog].project_label` and `default_priority`, resolved by `managed_task.authoring_config`. In an operator-enabled checkout these mirror the external operator config. Connected ChatGPT cannot read an untracked file, but the protocol already has an operator-owned channel for routing: the Project parameters. The operator fills that channel with the output of `requirement_intake.py routing-parameters` run in the target's checkout. That is the same resolver `create` uses, so no second source is created. Public source contains no concrete label, priority or operator path; the helper only prints what the local config says.

## Resolver

`resolve_connected_routing(*, target_repository, backlog_repository, committed_config, project_parameters, priority=None)` returns `(project_label, priority_label)` or raises:

1. If `committed_config` (the target's committed `[development_backlog]` table) is present, validate it: repository equals `backlog_repository`, `project:<slug>` format, `P0..P3` default. If `PROJECT_LABEL` or `DEFAULT_PRIORITY` are also declared and differ, raise a conflict. Use committed values.
2. Otherwise require `BACKLOG_REPOSITORY == backlog_repository`, `TARGET_REPOSITORY == target_repository`, a valid `PROJECT_LABEL` and a valid `DEFAULT_PRIORITY`. Anything missing or invalid raises.
3. An explicit `priority` overrides only the default and is validated by `priority_label`.

## Read-back

Extract the pure label check from `_reconcile_requirement_labels` (`requirement_label_problems(labels, project_label, priority_label)` → conflicting / missing) and use it in both paths. The local repair-then-verify flow keeps its behavior.

## Protocol

The Project parameters section gains `DEFAULT_PRIORITY` and names `routing-parameters` as the way to produce the parameters. The Requirement fixation section replaces "committed only" with the ordered resolution and the conflict rule. Read-back text is unchanged.
