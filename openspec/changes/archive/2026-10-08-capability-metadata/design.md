## Context

`template/scripts/capability_manager.py:evaluate_existing` loads a fixture through `capability_evals.load_fixture`, requires `loaded["capability"]` to equal the capability id and `loaded["content_sha256"]` to equal `capability.provenance["content_sha256"]`, then runs the shared core; a hash mismatch raises `CapabilityError("eval fixture content hash does not match the canonical capability descriptor")`. `load_descriptor` already requires `provenance.content_sha256` to equal the sha256 of the instruction file.

Verified defects on main (bd7f234):
- `dev-platform/evals/add-intents-pilot.json` and the template copy carry `6e3c711b...`; `dev-platform/capabilities/add-intents.toml` carries `b3889d76...` (the instruction hash). Commit e3484b2 (BR-353) rewrote the ADD freshness paragraphs of `add-intents.md` and updated the descriptor hash but not the fixture. A scripted sweep shows add-intents is the only stale fixture among the 13 per tree.
- `interoperable-agent-handoff-pilot.json` case `negative-start-managed-task` has prompt `example/development-backlog#123` in source and `example-org/development-backlog#123` in the template. The prompt digest is part of the reviewed fixture, so the two differ in meaning for the Claude-native `prompt_sha256` binding.
- No guard: `capability_manager.py validate/audit` never load fixtures, and `tests/test_template_contract.py` only asserts a handful of fixture paths exist/mirror. `tests/test_capability_manager.py` evaluates only its own temporary fixtures.

There is no fixture regeneration tool: fixtures are hand-authored reviewed data whose `content_sha256` is the binding to a reviewed descriptor revision (see docs/engineering/engineering-capabilities.md, "Provider-neutral evals"). Re-baselining means reviewing the descriptor change against the fixture cases and then updating that one digest.

## Goals

- Correct the stale binding and the source/template divergence.
- Make staleness or divergence of any shipped fixture fail CI with a message naming the fixture.
- Stay within data fixes plus one test; no downstream behavior change.

## Decisions

1. Re-baseline by editing only `content_sha256` of the add-intents fixture in both trees, and only after reviewing the e3484b2 diff of `add-intents.md`: it narrows ADD freshness wording (source-bound freshness instead of worktree-HEAD freshness) and does not alter the trigger/not-trigger boundary exercised by the 20 cases or the `quality_comparisons` verifier text. The hash value is read from the descriptor (`provenance.content_sha256`, equal to sha256 of the instruction file), never invented. If the review finds a case invalidated, the case is updated in the same change instead of only the hash.
2. For interoperable-agent-handoff, choose one prompt text for both trees. The placeholder repository name is fixture data only (no resolution); choose the template spelling `example-org/development-backlog#123` (the downstream-shipped, more conventional placeholder) and update source to match, then check no `prompt_sha256` pin of this fixture exists elsewhere (grep tests/docs) before changing it.
3. Regression is a test, not a new `validate` behavior: add to `tests/test_capability_manager.py` a test that, for each root in (`dev-platform`, `template/dev-platform`), iterates `sorted(evals/*.json)`, loads the descriptor `capabilities/<capability>.toml` via `capability_manager.load_registry`-compatible loading on that root, and calls `evaluate_existing(capability, fixture, runtime="fixture", runs=3)`; any `CapabilityError` fails the subtest naming root and fixture. A second assertion compares the sorted file names and the bytes of both trees' `evals/` directories. Rationale: `validate/audit` run in downstream projects that may not ship every fixture, and evaluation is a platform-source release concern; the test already runs under `scripts/run_test_groups.py --all`. A missing descriptor for a fixture, an unreadable fixture or a fixture without a descriptor fails explicitly (no skipping).
4. The heterogeneous `evidence` field (`none`, `deterministic-fixture`, path) is left untouched. It is catalog metadata displayed by `catalog_entry`; normalizing would change descriptor bytes, and therefore `content_sha256`-independent but template-mirrored files in every downstream project, for no defect. It is recorded as a follow-up observation only.
5. Copier impact: `template/dev-platform/evals/` is not in `_skip_if_exists`, so `copier update` overwrites downstream fixtures with the corrected ones; downstream descriptors are also template-managed, so hashes stay mutually consistent. No migration is needed.

## Risks

- A stale downstream fixture could not be repaired by a hash-only edit if the descriptor semantics changed; mitigated by the case review in decision 1.
- The new test will fail for any future descriptor edit that forgets the fixture, which is the intended friction; the failure message names the fixture and states the mismatch.
- Evaluating all fixtures adds runtime; the fixture runtime is deterministic and in-process, so the cost is small.

## Verification

Run the new test and the full group runner; demonstrate the guard by temporarily corrupting one hash in a scratch copy (not committed) or by a test that evaluates a deliberately stale temporary fixture and asserts the explicit mismatch error. Run the two documented `evaluate` commands for add-intents. `verification.md` records the actual commands and the case review result.
