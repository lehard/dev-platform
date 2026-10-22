## Context

`archive_change` (portable, platform-owned, not coordinator-managed) runs `select_checks.py --base origin/main --execute --evidence <change>/automated-checks.json`. The evidence it writes (version 2 in a managed checkout) records `selection`, `outcome`, `executed_commands`, `selected_checks`, `managed_checkout` and `gate_task_content` (`task_content_identity.review_content_identity`: digest over task-owned paths with lifecycle-only paths excluded, plus `base` = merge base of `HEAD` with `origin/main`).

`finish_task.py main()` for a managed delivery calls `require_automated_evidence(delivery.path, root=work)`: verification.md cites the evidence, selection `ready`, outcome `success`, command count equal to the selection, no failed command, and `evidence_matches_checkout` (same managed checkout, equivalent task content; the archive materialization and lifecycle evidence are the only accepted additions). It then fetches main, runs the consolidated completion preflight (`observe_completion_blockers`: hygiene, friction checkpoint, cleanliness, task freshness, branch staleness, scope overlap) and calls `run_checks(work, remote_main, args.no_checks)`, which always executes `select_checks.py --base <remote main> --execute`.

## Goals / Non-Goals

Goals: one full local execution per validated tree over `archive -> finish` in `portable`; an explicit, auditable reuse decision built only from existing evidence; every change to code, tests, base, configuration or selected commands forces the required validation.

Non-goals: changing the coordinator lifecycle, the check set, `select_checks.py` selection rules, GitHub PR CI, the machine pool or the duration of the checks; downstream rollout.

## Decisions

1. **Where the decision lives.** A function `automated_evidence_reuse(change, root, base_ref) -> CheckReuse` in `openspec_lifecycle.py`, next to `require_automated_evidence`, returns `reused` or `not-reusable` with a named reason and the facts used. `finish_task.py` calls it only when `lifecycle_mode(config) == "portable"`, the delivery is a managed change (`delivery is not None`, not queue-merged) and `require_automated_evidence` already passed, after the completion preflight and immediately before `run_checks`. All other paths call `run_checks` unchanged. The coordinator path never reaches the helper.

2. **Exact validated base, stricter than review reuse.** Review evidence survives a clean, disjoint main advance because review judges the task patch. Checks test the integrated tree, so check reuse requires `gate_task_content.base == merge-base(HEAD, <remote main>)` and `<remote main>` to be an ancestor of `HEAD`. After any reconcile or main advance that changes the base, the evidence is not reusable and finish runs the checks. A child whose content identity is bound to a contribution or predecessor head (`_review_base` resolves another base) therefore does not match and runs the checks.

3. **Same required selection.** Finish recomputes the selection it would execute with `select_checks.py --base <remote main> --json` in the same mode (`local-affected`). The selection must be `ready`, and every command it selects must be present in the evidence's `executed_commands` with outcome `success`. A selection that now requires a command that did not run (for example a changed `checks.toml` mapping reaching the archive paths) is not reusable. Recomputation runs no command and takes no machine-pool lease.

4. **Evidence version.** Version 1 evidence (no `managed_checkout` / `gate_task_content`) is not reusable; the reason names the missing field and the checks run. Unreadable or failed evidence never reaches this decision: `require_automated_evidence` stops publication first, as today.

5. **Visible outcome.** One line `DEV_PLATFORM_CHECK_REUSE: {"decision": "reused"|"not-reusable", "reason": ..., "evidence": path, "validated_head": ..., "base": ..., "commands": [...]}` is printed before publication. The finish stage marker reads `preflight clear: reusing archive check evidence` or the existing `preflight clear: starting required validation`.

6. **No fallback semantics.** `not-reusable` is not a recovery from an error: running the required validation is the contract's default, and the reason is printed. Any error inside the decision (git failure, unreadable selection output) is raised as a named failure and stops finish; it is not turned into a silent rerun.

## Risks / Trade-offs

- Lifecycle-only paths excluded from the content identity (verification receipt, check and review evidence, the change's own materialized `openspec/specs/<capability>/spec.md`) change after the checks ran. A check that reads those files is not re-executed locally. Mitigation: this is the same exclusion set the existing evidence contract already accepts; OpenSpec hygiene still runs in finish, and the exact-head PR CI still runs every required check.
- Recomputing the selection costs one `git diff` and a config read.

## Migration

The change ships in the template. A project picks it up through the ordinary release and Copier update; evidence produced by an older template (version 1) is simply not reusable, so the first finish after the update behaves as before. No downstream configuration is added.
