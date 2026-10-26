## Why

A full selected-check run takes about 20 minutes. Two cheap, deterministic blockers are discovered only after it: a managed run started without `--evidence` is refused at handoff ("missing automated-checks.json"), and ticking the last `tasks.md` box after the run changes task content and forces a second full run. A stale generated manifest fails only after the full test run because `generate_platform_manifest.py --check` is last in the full set.

Slice 1 of Requirement BR-773; the split into small children is a technical decision of the backlog-revision session (2026-10-26). Evidence reuse across `archive`/`finish`, refusing a repeated run of identical content and the private-reference guard in `select_checks` stay for a later child.

## What Changes

- `select_checks.py --execute` in a managed checkout refuses before any command when `--evidence` is missing or the change is not archive-ready (reusing `openspec_lifecycle.archive_content_problems`).
- `dev-platform/checks.toml` runs `generate_platform_manifest.py --check` before `run_test_groups.py --all` in the full set.

## Impact

- `template/scripts/select_checks.py`, `dev-platform/checks.toml`, tests, generated platform manifest.
- Spec `completion-lifecycle`: one added requirement.
