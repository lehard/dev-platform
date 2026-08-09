# Verification: align self-contained CI contract

## Result

Semantic review: **PASS**.

The change is documentation/configuration coherence only. Generated instructions now match the self-contained downstream CI behavior shipped in v1.0.1; no lifecycle or CI execution logic changes.

## Completeness and correctness

- AGENTS no longer says downstream CI executes `platform_ci_ref`.
- README states CI is local, Copier-managed, and has no private cross-repository workflow dependency.
- Copier help identifies `platform_ci_ref` as legacy schema-v2 metadata.
- Regression tests assert this contract.
- Platform CI run #23 passed on `e0a775bdb1be9f4b2b6aaef28816629ba18bae1c`, including all three fresh-render profiles and Copier upgrade smoke.

## Coherence

The docs now describe the same propagation boundary as the implementation: platform changes are distributed through reviewed Copier releases, while downstream CI executes only files already present in the downstream repository.

The GitHub connector cannot literally invoke `/opsx:verify`; this record documents the equivalent completeness/correctness/coherence review without claiming the slash command ran.
