## Why

Tests prove behavior but not that a series of AI-generated changes is slowly bloating code or concentrating complexity. The TeamAI pilot (Requirement #228, decision 0001) found TeamAI unsuitable as a whole dependency but showed its Code Erosion workflow is independent and reusable. Dev Platform's own code is Python, which is exactly the language `scb-check` (SlopCodeBench) is calibrated for.

## What Changes

- Add an independent `Code Erosion` GitHub workflow that runs the pinned upstream `scb-check` on `scripts/` and `template/scripts/` for each pull request and publishes an informational report.
- Add a thin, tested report renderer (formatting only; no analysis) that emits a marker-keyed Markdown report, including the top complexity hotspots reported by the upstream tool and explicit applicability caveats.
- Post/update one PR comment identified by a marker; when that is impossible (fork token, API error) the report stays in the job summary. The job never fails on findings, tool exit 1, or renderer/comment errors.
- Pin `scb-check` in one repository-owned version file, and pin all actions by SHA. Version bumps are normal reviewed changes.
- Document limits and an initial Dev Platform baseline in `docs/engineering/code-erosion.md`, plus one pointer row in `AGENTS.md`.

## Impact

Central `lehard/dev-platform` CI only. It adds a separate non-required workflow: existing required checks, publication queue and merge policy are unchanged. No managed-project template rendering changes in this iteration. No dashboard or telemetry backend.

## Outcome evidence

Success is observable: a dogfood PR (this change's own) shows the report comment/summary with baseline-comparable numbers and named hotspots, and re-pushing updates the same comment.

## Non-goals

No blocking threshold, no own analyzer, no cross-language quality score, no template rollout to downstream projects.
