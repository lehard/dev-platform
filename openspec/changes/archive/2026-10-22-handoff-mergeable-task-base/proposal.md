## Why

A coordinator candidate that is behind `main` can be handed off today only under the behind-disjoint contract: the files `main` changed since the merge base must be disjoint from the task's files and a trial merge must be clean. The generated platform manifest (`template/dev-platform/platform-manifest.json`) is rewritten by almost every PR that touches `template/`, so the overlap almost always exists. Each `main` advance during a developer's full validation forces a reconcile and a new ~25-minute run. On 2026-10-21 lehard/dev-platform#629 needed four reconciles. The publication queue already merges any clean result and gates on required checks of the integrated head, and path overlap alone does not block it, so the stricter developer gate only costs time.

## What Changes

- The coordinator handoff contract becomes **behind-mergeable**: a head behind the observed `main` passes when `git merge-tree` of head and `main` is clean, or conflicts only in declared generated files. A path changed on both sides no longer blocks by itself. A conflict in any other file still blocks before any expensive command, naming the files and the reconcile command.
- Projects declare generated files in their committed check configuration (`[[generated_files]]` with `path` and a `regenerate` command). The gate reads the declaration only from the observed `main` commit, so a candidate cannot declare its own conflict generated. A malformed declaration fails explicitly; no declaration means no generated files.
- Dev Platform declares `template/dev-platform/platform-manifest.json`; its generator gains `--root` so the declared command can regenerate another tree from trusted code.
- Selected-check evidence records `task_base` with the behind-mergeable contract, the observed main, the merge base, paths changed on both sides and generated-file conflicts. Evidence recorded earlier under behind-disjoint stays valid (nothing validates the contract name).
- Status and reconcile report `behind-mergeable` as not requiring reconcile. Non-coordinator tasks keep the fresh-base gate.

## Impact

- `template/scripts/_platform_common.py` (classification, declaration reader), `select_checks.py`, `project_publish.py`, `finish_task.py`, `task_reconciliation.py`.
- `dev-platform/checks.toml` (declaration), `scripts/generate_platform_manifest.py` (`--root`).
- Docs: `docs/engineering/agent-workflow.md`.
- Until the queue-side regeneration change lands, a candidate admitted with a manifest conflict reaches the existing integration repair; no gate is weakened.
