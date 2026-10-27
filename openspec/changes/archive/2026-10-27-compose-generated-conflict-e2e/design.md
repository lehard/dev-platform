## Context

`publication_queue.worker` → `_integrate` → `_prepare` routes a candidate to `post_review_finalization.prepare_derived_specs` when main and the candidate both changed a declared generated file or the merge conflicts only in derived paths. For a `requirement/BR-*` head with archived deltas, `rederive_archived_specs` takes the composition branch: it reads the owned manifest under `dev-platform/requirement-integrations`, replays the archived deltas in manifest child order, proves `composition_identity` unchanged and pushes with `push_fast_forward`.

## Decisions

- **Real git, faked GitHub.** The remote, the composition branch, main and the trusted checkout are real repositories; `_pr`, `_comments`, `_gh` (compare inventory and comments), labels and the merge `gh api` call are faked, as in the existing `Multi` fixture. The source URL for the derivation is redirected to the local bare remote through `prepare_derived_specs(source_repo=...)`.
- **Composition fixture.** The `Repository` builder of `tests/test_requirement_contribution_composition.py` creates the sealed manifest and two integrated children; the first child also changes the generated manifest; children are archived with delta specs as finalization leaves them.
- **Boundaries kept mocked, each covered elsewhere.** Composition final-gate proofs (`require_composition_finalized`, `refresh_composition_checks`), the required-check observation, and the OpenSpec CLI calls: the archived-delta replay uses a deterministic fixture replay equal to the CLI result for capabilities main did not touch, and validation is a no-op (CLI replay is covered by `RederivationTests`, which needs the CLI). CI does not install the OpenSpec CLI for unit tests, so the test must not depend on it.
- **Generator.** A small fixture generator writes the JSON manifest from the tree; it runs from the trusted checkout, never from the candidate.

## Risks

- If the test exposes a defect in the composition derivation, the fix is a production change: stop and return to the coordinator before widening scope.
