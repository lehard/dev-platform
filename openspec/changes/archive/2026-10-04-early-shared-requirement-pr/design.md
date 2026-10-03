# Design: Early draft shared PR

## Identity and append-only growth

The candidate keeps the existing stable branch `agent/requirement-<n>-<hash>-integration[-<generation>]` and manifest path. The manifest gains optional `expected_changes`, the ordered mandatory changes still to deliver (taken from the authored handoffs, excluding children already delivered), and a derived `complete` flag, true only when `children` equals `expected_changes`. Children must always be an ordered prefix of `expected_changes`. A manifest without `expected_changes` is a legacy complete manifest and behaves exactly as before.

Branch history is a sequence of child commits, each carrying the existing provenance message, with bind commits (`Bind integrated Requirement <id> candidate`, touching only the manifest path) after them; the tip is always a bind commit. A one-shot candidate is `child…, bind`. An early candidate grows as `child1, bind1, child2, bind2`. Every bind records a manifest whose children are an exact prefix of the next and whose base is unchanged. History is never rewritten and every update is a fast-forward push. Reordering, replacing or removing a child, a changed child head or any extra commit is a blocker.

The candidate keeps its own `base`. For a candidate that already has commits, the base only has to remain the recorded ancestor; main advancing does not invalidate an append. Merging a stale PR remains with the existing protected publication primitives (publication queue/GitHub branch update). A brand-new candidate still requires its base to equal current main. The immutable-generation rule is unchanged for recovery from a failed or rebased-out candidate; an append keeps the same identity and the same PR.

The supervisor finds an existing candidate by scanning local `agent/requirement-<n>-<hash>-integration*` branches whose committed manifest children are an exact head-prefix of the ready receipts; zero matches creates a new one, more than one blocks.

## Publication

For an incomplete manifest `publish_candidate` does not run the local full-check suite (GitHub required checks run on the draft PR) and calls `project_publish.py --shared-manifest`. The publisher itself derives incompleteness from the committed manifest: it pushes the branch (an existing PR with a strict-ancestor head counts as the same PR, so no fresh-base requirement), ensures a draft PR with `gh pr create --draft`, skips Project "In review" attribution, merge arming and publication-queue admission, and returns. A divergent remote head blocks.

For a complete manifest the supervisor requires the Requirement retrospective checkpoint, `publish_candidate` runs the full checks on the exact head, and the publisher marks the existing draft PR ready with `gh pr ready` (no new PR) before the unchanged protected merge path. The terminal reconcile (`_reconcile_exact_merged`) refuses an incomplete manifest even if its PR was merged by other means.

`PR_VIEW_FIELDS` gains `isDraft`.

## Supervisor

`advance` stays resumable. In the child loop, when at least one child is ready, the Requirement has two or more mandatory changes and the next child is not ready, it first composes or appends and publishes the draft, then starts or resumes the next child and returns `implement-child` including the draft PR identity. When every child is ready it performs the complete publication exactly as before. A Requirement with a single mandatory change keeps ordinary managed publication.

## Failure behavior

Unreadable PR state, a changed child head, an overlapping path, an ambiguous candidate or a failed check stops before any ready transition and leaves the draft as is. A draft with failing GitHub checks is allowed and visible; it never advances any status.

## Release and rollout

After the exact merge, the existing release PR (`VERSION` bump), immutable tag and managed rollout are used unchanged. This change adds no new subsystem; the execution task records the resulting release and rollout outcome or the explicit blocker.
