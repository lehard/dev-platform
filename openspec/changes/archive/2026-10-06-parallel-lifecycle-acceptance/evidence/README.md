# Dogfood run evidence (template, no run recorded yet)

The real run is deferred to BR-391 (after BR-353 merges); this change delivers only this template. The run must be one real run on a real repository with several overlapping PRs, main movement, at least one genuine repair and successful merges. Nothing below has been observed yet: replace each placeholder with observed data and leave a missing item as an explicit gap. Never infer, backfill or paraphrase a missing marker; redact secrets without inventing replacement observations.

The sandbox scenario's injected finding does not count as a real finding. If the real run has no genuine repair, record that limitation and leave acceptance pending.

## 1. Run manifest (`manifest.json`)
- Repository, parent Requirement, child issues and PR URLs; implementation revision of the platform under test.
- Configuration in force: reviewer providers and models, coordinator App slug, writer command and allowed paths, claim TTL, required checks.
- Start and end timestamps; initial and final `main` SHAs.

## 2. Ordered lifecycle timeline (`timeline.md`, generated, not hand-written)
Generate from observed markers and refs: coordinator records, claim and result markers with original comment IDs, exact head SHAs, task identities, attempts and outcomes, in comment order. Preserve provenance (link or digest of each source comment). Interrupted jobs, missing markers and manual interventions stay explicit gaps.

## 3. Receipts, by link or digest
- Required checks per exact head, both independent review perspectives and their findings, and the repair commits.
- Archive and verification receipts, merge commits, post-merge retrospectives, terminal reconciliation and cleanup results.

## 4. Operator-action record (`operator-actions.md`)
Every human or operator action from developer handoff to completion, with time and reason; an empty record must be stated, not omitted. "No manual completion pass" requires this record plus the automated receipts above, not merely an absence of comments. Developer semantic-verification handoffs after repaired content are a developer action by contract, not an operator completion pass; list them separately.

## 5. Known cases to look for
- Integration repair that changes task content of an already finalized candidate: it must be re-reviewed against the archive and finalized again (fixed offline; confirm on the real run).
- Squash merge, stale-head refusals, branch protection refusals and CI latency, none of which the offline sandbox can prove.

## 6. Conclusion
State what was observed, which fixture assumptions held, and which gaps remain. Do not claim acceptance when a section above is incomplete.
