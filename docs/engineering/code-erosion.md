# Code erosion signal

An informational pull-request signal about gradual code-quality erosion (redundancy,
duplication, complexity concentration), most useful for agent-generated changes.
Accepted behavior: `openspec/specs/code-erosion-signal/spec.md`. Decision lineage:
reused from the TeamAI pilot ([0001](../decisions/0001-teamai-substitution.md)); only
TeamAI's independent Code Erosion workflow is adapted, not TeamAI itself.

## What runs

`.github/workflows/code-erosion.yml` runs upstream
[`scb-check`](https://pypi.org/project/scb-check/) (SlopCodeBench) through
`uvx` at the exact version in `.github/code-erosion/scb-check-version.txt`, over
`scripts/` and `template/scripts/` (shipped code; tests and fixtures are not scanned).
`scripts/code_erosion_report.py` only formats its output. There is no own analyzer.

The report is one PR comment identified by `<!-- code-erosion-report -->`, updated on each
push, and is always written to the job summary (the fallback for fork PRs or API errors).
The workflow is not a required check, sets `continue-on-error`, swallows the tool's
exit code and touches no publication or merge policy. It does not replace tests, lint or
verification.

## Reading it

- Values are heuristics, **not a quality score**. Upstream reference bands are
  Python-calibrated and are deliberately not shown as thresholds; never apply them to
  other languages or projects.
- Read the *trend and the named hotspots* against the baseline below, not the absolute number.
- Erosion measures the share of code mass in high-complexity functions; a single very
  large legacy function dominates it. Lower is not automatically better.
- Before scanning any non-Python area, state its applicability limits here first (the
  upstream ast-grep verbosity rules are Python-only).

## Baseline

Measured with `scb-check==0.2.0` at main `d61e65f` (2026-09-28):

| Area | Verbosity | Erosion | Cognitive erosion | Files | SLOC | High-CC functions |
|---|---|---|---|---|---|---|
| `scripts` | 0.045 | 0.441 | 0.569 | 59 | 4062 | 21/214 |
| `template/scripts` | 0.068 | 0.667 | 0.797 | 60 | 21011 | 178/1059 |

Largest existing hotspots: `finish_task.py:main` (complexity 89),
`add_intents.py:validate_intents` (82) and `_validate_add_document` (63),
`rollout_project.py:migrate_project_publication_safety` (36).

## Updating the tool

Change the version file (exact `X.Y.Z`) in an ordinary reviewed PR, re-run both scans,
compare against this baseline, refresh it if the tool's metric definitions changed, and
update the renderer if the JSON schema changed. Never use a floating version.
