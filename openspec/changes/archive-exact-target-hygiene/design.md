## Context
`archive_change` runs `select_checks.py --execute` as a child process; the mapping's commands (including `openspec_lifecycle.py check`) are fixed, project-owned and must keep working unmodified downstream.

## Decisions
1. Transport: archive sets `DEV_PLATFORM_ARCHIVE_TARGET=<change>` only in the environment of that one `run_checked` subprocess (never `os.environ` of the parent), so the context dies with the child and nothing persists on failure.
2. Hygiene semantics: when the variable is present, `check_hygiene` requires it to name an existing active change with all tasks complete; otherwise it fails with a message naming the problem (no silent ignore, no default). It then excludes exactly that name; any other completed active change still blocks, in both candidate and integration stages.
3. Single implementation in the template script, which source `scripts/openspec_lifecycle.py` already delegates to, so source and rendered projects behave identically.
4. BR-353 compatibility: `--finalize` reuses evidence and does not run checks, so it needs no exemption; a future finalizer that runs checks sets the same target through the same helper rather than adding a second bypass.

## Risks and Mitigations
A stray exported variable could exempt one change: it is validated against an existing completed active change, exempts one name only, and archive itself still requires verification, review and evidence gates. Documented as a reserved variable.

## Verification
Unit tests for check_hygiene; end-to-end test in a temp git repo using the real template `checks.toml` mapping reproducing the old deadlock and the fix; negative cases (second stale change, nonexistent/invalid target, failed archive leaves no bypass, post-archive check passes).
