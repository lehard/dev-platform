## Context

- `private_lineage.enabled(root)` reads the optional `[private_lineage]` table; `private_lineage.require_clean_candidate` already fails when enabled and the guard is missing (used by `select_checks --execute`).
- `finish_task.observe_private_reference_blocker` has three callers (preflight, developer handoff, publication recheck) and returns `None` when the guard file is absent. `project_publish._safe_presentation` and the publish path skip the guard the same way.
- `select_checks.changed_files` unions `base...HEAD`, unstaged and staged diffs, ignores non-zero git exits, and with no base and an empty result diffs `HEAD~1..HEAD`. `scripts/select_checks.py` checks `--base` only after the selector ran.

## Decisions

- **Guard by configuration, not by file presence.** A single `private_lineage.guard_command(root)` returns the guard path when enabled, raises `PrivateLineageError` naming `scripts/check_private_backlog_refs.py` when enabled and missing, and returns `None` when disabled; every caller prints the "not applicable by configuration" line on `None` and passes nothing silently.
- **Base resolution.** `resolve_base(root, base, explicit)`: explicit files win; an explicit `--base` is used; otherwise the current branch must be a named branch other than `main_branch`, and the base is `origin/<main_branch>` (the task base every lifecycle path already uses). Main or detached HEAD fails: "pass --base <ref> or --changed-file <path>". protected-full needs no base.
- **Git failures are errors.** Every `git diff` in `changed_files` uses `check=True` semantics and fails naming the command.
- **Friction staleness.** Reproduced: `current_task_content` caught every exception and returned `None`, so an unreadable task state or proof read as a stale checkpoint. The catch is removed; `None` remains only for a quick task without managed state (legitimate absence: exact-head semantics apply). Freshness across a lifecycle-only head change is already tested.

## Fail-open inventory

- `finish_task.observe_private_reference_blocker` missing guard: FIXED (blocker when enabled; explicit not-applicable line when disabled).
- `project_publish` `_safe_presentation` and publish path missing guard: FIXED (same).
- `select_checks.changed_files` ignored git exit codes: FIXED (error naming the command).
- `select_checks.changed_files` `HEAD~1..HEAD`: FIXED (task-branch base or explicit error).
- `scripts/select_checks.py` base check after the selector: FIXED (resolved before).
- `agent_friction.current_task_content` `except Exception: return None`: FIXED (error propagates). No managed state for a quick task: LEGITIMATE ABSENCE (explicit `None` branch; the checkpoint then binds the exact head).

## Risks

- CI installs the source contract without `[private_lineage]`, so finish-style guards there report not applicable; the CI `validate` job runs `scripts/check_private_backlog_refs.py` directly, and the publication queue does not call these guards.

- Projects scripting `select_checks.py` on main without `--base` must add it; the error names the option.
