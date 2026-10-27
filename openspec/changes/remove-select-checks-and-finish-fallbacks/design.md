## Context

- `managed_project_status.py` is a managed template script listed in `platform-manifest.json`; Copier updates managed scripts together, so a project cannot have the new `select_checks.py` without it.
- `check_private_backlog_refs.py` lives only in the platform source (`scripts/`), not in `template/scripts/`. The established explicit rule is `private_lineage.require_clean_candidate`: enabled -> the guard is required, missing -> `PrivateLineageError`; disabled -> not applicable. `select_checks` already follows it.
- `finish_board` is called after publication in four paths; only the developer-handoff path checks the release result.

## Decisions

- **Direct import.** No stub: an absent module is a broken installation and the import error names it.
- **One rule for the guard.** `observe_private_reference_blocker` uses `private_lineage.enabled`. Enabled without the script returns the blocker "private lineage is enabled but scripts/check_private_backlog_refs.py is missing"; disabled returns `None` because configuration makes the guard not applicable, not because a file is missing. The dev-platform operator contract enables private lineage, so the guard keeps running here.
- **Board release is strict everywhere.** An unreadable or malformed board names its path; a failed `agent_board.py finish` names the claim and the rerun command. Legitimate absence (inventoried): no board file means no claim was ever recorded on this machine, and no item for the worktree means the claim was already released (finish is resumable); both return "no claim" through an explicit branch and substitute nothing.

## Risks

- A finish that previously ignored a failed board release after a merge now stops with the rerun command; finish is resumable, so a rerun completes it.
