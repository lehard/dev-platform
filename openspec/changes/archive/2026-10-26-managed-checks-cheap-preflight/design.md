## Context

`select_checks.main` already resolves `require_managed_checkout_identity` before any command and runs freshness and scope gates before `execute`. `openspec_lifecycle.archive_content_problems` is the canonical archive-readiness check (complete tasks, authored Purpose for a new capability) without Git or the OpenSpec CLI.

## Decisions

- Add the two refusals right after the managed checkout identity is resolved, before quick/freshness/scope gates and the precheck. Applies only to a managed checkout whose change is still active; quick tasks, coordinator disposable checkouts (no managed identity) and post-archive completion runs (portable `finish` runs `select_checks --execute` without `--evidence` after archive) are unchanged.
- Reuse `archive_content_problems` instead of a new tasks parser, so the preflight and archive cannot disagree.
- Reorder the platform's own `full_commands` (and the parallel `full_evidence_types`) so the manifest check precedes the full test run; the set of required checks is unchanged (BR exclusion).

## Risks

- A managed run used only for local feedback now needs `--evidence`; plain feedback stays available through `run_test_groups.py` or `select_checks` without `--execute`.
