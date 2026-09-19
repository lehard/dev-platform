# Proposal: Finalize the public snapshot identity boundary

## Why

Development Backlog #122 made the fresh public snapshot self-contained and removed private-project behavior from the rollout core. The remaining cutover boundary still embeds two pieces of operator history into the shipped product:

- the maintainer's concrete Development Backlog repository is treated as a canonical public-product repository even though Development Backlog is an optional operator integration;
- the shipped sanitizer contains the names of known private downstream projects in compatibility-marker patterns, even though those names are needed only to sanitize the old source before fresh-history cutover.

A final public snapshot should contain the generic capability and its tests/specs, but not the current operator installation or the operator's historical downstream names.

## What Changes

- Remove the concrete Development Backlog repository from public-product identity and replace generic test/spec fixtures with synthetic repositories or operator-provided values.
- Keep Development Backlog as an optional capability whose actual repository/project identity comes only from external operator configuration.
- Separate reusable public sanitization rules from one-shot cutover deny data.
- Allow a bounded external cutover policy/input to add private repository/name markers without copying that policy into the snapshot.
- Keep deterministic candidate-set, source-completeness, history-secret, and snapshot-smoke guarantees from #122.
- Produce an explicit operator handoff checklist for the current installation without committing live operator values.

## Impact

- `scripts/public_distribution.py` policy/input boundary and tests.
- Synthetic fixtures in public tests and accepted specs.
- Operator/backlog documentation and Project Factory contract wording where concrete installation identity leaked into generic product evidence.
- Cutover runbook.
- No repository-admin mutation, downstream migration, or private operator file is performed or committed by this change.
