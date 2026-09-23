# Design: One intake meaning across accepted and agent surfaces

## Contract changes

Replace stale generic-fixation requirements in accepted OpenSpec with the current requirement-first route. Keep technical package requirements scoped to internal children and explicit direct technical tasks. Correct adjacent specs that refer to fixation as direct managed-task authoring.

## Drift guard

Add a focused repository test that reads a bounded set of canonical and rendered agent surfaces plus relevant accepted specs. Assert positive route semantics and reject specific stale generic-fixation claims. The guard is semantic at the contract boundary, using representative phrases and required relationships rather than a full natural-language parser. It runs in the existing test groups.

## Compatibility

No runtime intake API or package format changes. Downstream rendered instructions receive the same clarification through normal immutable release and Copier update. Existing internal technical tasks retain their lifecycle.
