## 1. Reviewer runtime usage

- [x] 1.1 Parse runtime-returned usage in `independent_review_runner.run_perspective` (Claude print JSON; Codex single `turn.completed`) into an optional runtime-local `runtime_usage` block on available reports; unknown on anything unsupported; no cost fields.
- [x] 1.2 Make report validation accept reports with and without the block; the block never affects acceptance, freshness or disposition binding.

## 2. Requirement metrics command

- [x] 2.1 Add `template/scripts/requirement_metrics.py` and `scripts/requirement_metrics.py` with `report` and `aggregate`, JSON and text output, `--offline`, `--claude-projects-dir`; read-only, stdout only.
- [x] 2.2 Implement the `{value, status, sources}` model with unknown/partial propagation and exact child/routing/archive resolution.
- [x] 2.3 Implement cycle/stage, routing/provenance, verification/full-validation, publication, CI, friction and human-stop sections.
- [x] 2.4 Implement independent review round reconstruction from published PR history with rerun cause classification and post-review validation/CI cycles.
- [x] 2.5 Implement the counters-only Claude Code session adapter with exact attribution; other runtimes unknown.
- [x] 2.6 Implement aggregate rows, comparable groups with sample adequacy, runtime-keyed groups and advisory note.

## 3. Evidence and documentation

- [x] 3.1 Add unit tests (fake `gh`, temporary sources) for every section, unknown/partial semantics, privacy (no text in output) and runtime usage parsing; register them in a test group.
- [x] 3.2 Document the command in the engineering workflow documentation and its template mirror.
- [x] 3.3 Dogfood `report` on an already completed Requirement and `aggregate` over at least two, and record traceability in `verification.md`.
- [x] 3.4 Run selected and required platform checks, semantic OpenSpec verification, a truthful receipt, archive and managed publication.
