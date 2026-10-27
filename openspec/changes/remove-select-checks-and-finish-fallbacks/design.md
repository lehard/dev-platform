## Context

- `managed_project_status.py` is a managed template script listed in `platform-manifest.json`; Copier updates managed scripts together, so a project cannot have the new `select_checks.py` without it.
- `finish_board` is called after publication in four paths; only the developer-handoff path checks the release result.

## Decisions

- **Direct import.** No stub: an absent module is a broken installation and the import error names it.
- **Board release is strict everywhere.** An unreadable or malformed board names its path; a failed `agent_board.py finish` names the claim and the rerun command. Legitimate absence (inventoried): no board file means no claim was ever recorded on this machine, and no item for the worktree means the claim was already released (finish is resumable); both return "no claim" through an explicit branch and substitute nothing.

## Risks

- A finish that previously ignored a failed board release after a merge now stops with the rerun command; finish is resumable, so a rerun completes it.
