## Context
`archive_change` runs `select_checks.py --execute` as a child process; the mapping's commands (including `openspec_lifecycle.py check`) are fixed, project-owned and must keep working unmodified downstream.

## Decisions
1. Transport: archive sets the reserved pair `DEV_PLATFORM_ARCHIVE_TARGET=<change>` and `DEV_PLATFORM_ARCHIVE_ROOT=<realpath of the archiving checkout>` only in the environment of that one `run_checked` subprocess (never `os.environ` of the parent), so the context dies with the child and nothing persists on failure. The root binds the exemption to the checkout it was issued for, because the whole validation process tree (including tests that run hygiene on other temp repositories) inherits the pair.
2. Hygiene semantics: if exactly one of the pair is set, `check_hygiene` fails explicitly (malformed context). If both are set and the realpath of the root being checked differs from `DEV_PLATFORM_ARCHIVE_ROOT`, the context belongs to another checkout: hygiene runs as the ordinary check, with no exemption and no error (this is scoping, not a masked failure). If the roots match, the target must name an existing active change with all tasks complete, otherwise hygiene fails with a message naming the problem (no silent ignore, no default); exactly that name is then excluded, and any other completed active change still blocks, in both candidate and integration stages.
3. Single implementation in the template script, which source `scripts/openspec_lifecycle.py` already delegates to, so source and rendered projects behave identically.
4. BR-353 compatibility: `--finalize` reuses evidence and does not run checks, so it needs no exemption; a future finalizer that runs checks sets the same target through the same helper rather than adding a second bypass.

## Risks and Mitigations
A stray exported pair could exempt one change only in the checkout it names: it is validated against an existing completed active change, exempts one name only, and archive itself still requires verification, review and evidence gates. Documented as a reserved variable.

## Verification
Unit tests for check_hygiene; end-to-end test in a temp git repo using the real template `checks.toml` mapping reproducing the old deadlock and the fix; negative cases (second stale change, nonexistent/invalid target, failed archive leaves no bypass, post-archive check passes).
