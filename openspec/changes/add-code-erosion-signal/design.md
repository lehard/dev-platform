## Design

**Reuse, not reimplementation.** The analysis is upstream `scb-check==0.2.0` run through `uvx --from 'scb-check==<pinned>'`. The workflow shape (independent workflow, swallowed exit code, marker-keyed comment with job-summary fallback) follows TeamAI's `code-erosion.yml`. The renderer is a small Dev Platform script because the upstream renderer's license is unstated (repository license lookup returns NOASSERTION), so it is not copied; it only formats the tool's JSON and human output.

**Version pin.** `.github/code-erosion/scb-check-version.txt` holds the exact version; the workflow reads it, and a unit test asserts it is an exact `X.Y.Z` pin and that the workflow never references a floating tool version. Actions are pinned by commit SHA like `ci.yml`.

**Scope.** Scan `scripts` and `template/scripts` separately (test code and fixtures excluded) so each report row maps to a shipped code area. `--report` JSON provides metrics; the human output provides concrete function-level hotspots, parsed defensively for the top few.

**Never blocking.** Each step tolerates non-zero exit (scb-check exits 1 when it finds anything). The renderer always exits 0 and degrades to a warning on missing keys/garbled input. The comment step catches errors and warns. The workflow is not a required check and has no path to the publication queue.

**Honest reading.** Reference bands from upstream are Python-calibrated; the report shows raw values and states that they are heuristic signals, not a quality score, not comparable across languages/projects, and not a duplicate of tests/lint. It compares nothing against a threshold.

**Comment permissions.** `pull-requests: write` only; fork PRs get a read-only token, so the comment step degrades to the summary.

### Risks

Supply chain: an unpinned tool would silently change behavior — mitigated by exact pin + SHA-pinned actions + test. Noise: heuristic metrics can mislead — mitigated by informational framing and stated limits. CI cost: two short scans, non-required.
