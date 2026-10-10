## Why

Finalization of a reviewed coordinator candidate depends on `main` standing still. When a review repair changed task content, `post_review_finalization.reestablish_gates` reruns selected checks through `trusted_checks_runner`, which calls `select_checks --base origin/main --execute`; its task freshness gate (`_platform_common.require_fresh_task_base`) requires the head to contain current `origin/main`. Finalization deliberately never merges `main` (that is `publication_queue._prepare`, which runs after finalization), so any PR merged between review and finalization sends the candidate to `blocked-escalation`. This happened to lehard/dev-platform#455. The only exit, merging `main` and re-admitting the new head (v1.9.4), resets the review gates and reruns a full LLM review although the task content is unchanged. The candidate contour now carries the integration contour's job.

## What Changes

- `select_checks.py` gets an explicit, bounded coordinator-finalization freshness contract, `--proven-base SHA`. The head must fork from `SHA` on `origin/<main>` history (`SHA` equals `merge-base(HEAD, origin/<main>)`). The flag works only with `--execute`, in coordinator lifecycle mode, without `--evidence`, without `--contribution-base` and outside protected-full mode. Every misuse fails before any command starts. Without the flag the freshness gate is unchanged.
- `post_review_finalization` runs the real selected checks with `--proven-base` set to the task-content base of the identity, after that identity is proven equivalent to the candidate's recorded identity. The harness-executed gate evidence records the contract and the base. Ordinary finalization no longer requires `origin/main` freshness. The contribution path keeps `--contribution-base`. Finalization still never fetches or merges `main` and pushes only its own fast-forward archive commit.
- When a developer re-admits a descendant head in place of an admitted one (`publication_queue.admit` supersession, v1.9.4), the new review-pending record keeps every lineage gate that is still `reusable` for the new task-content identity. Required checks and the gates the new handoff supplies are not carried. A passed review is therefore reused by the existing review-job reuse path without launching a reviewer. Changed task content still requires a new review.
- The integration contour is unchanged and documented as the owner of base actualization. It prepares the candidate on current `main`, merges a clean result automatically, re-derives archive-derived specs, runs required CI on the actual merged head and offers integration repair on a real conflict or failing check.
- Documentation of the two-contour boundary, and the operator path that recovers #455 in place.

## Capabilities

### Modified Capabilities

- `completion-lifecycle`: finalization re-establishes checks on the proven base and never merges `main`; gate reuse covers re-admission with unchanged task content.
- `platform-lifecycle`: the expensive-validation freshness rule gains one bounded coordinator-finalization contract; developer preflight is unchanged.
- `publication-queue`: the integration contour alone actualizes the base after finalization, without developer involvement.

## Impact

`template/scripts/select_checks.py` (and a helper in `template/scripts/_platform_common.py`), `template/scripts/post_review_finalization.py` and `template/scripts/publication_queue.py`. Tests: `tests/test_select_checks.py`, `tests/test_post_review_finalization.py`, `tests/test_publication_queue.py`, `tests/test_pr_review_gate.py`, and the offline `parallel_lifecycle_acceptance.py` scenario. Docs: `docs/engineering/agent-workflow.md` and `docs/engineering/openspec-workflow.md`. `select_checks.py` is rendered downstream, but the new flag refuses outside coordinator lifecycle mode, so downstream behavior does not change. This change depends on the re-admission change (PR #457, v1.9.4) being on `main`.

## Non-goals

Removing duplicate full checks (BR-468); changes to downstream projects; a new coordinator, queue or review mechanism; merging `main` inside finalization; weakening developer preflight freshness, protected CI or the semantic-verification gate.
