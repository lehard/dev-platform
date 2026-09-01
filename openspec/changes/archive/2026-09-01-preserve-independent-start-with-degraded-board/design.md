# Design: Valid claims gate admission; degraded records remain diagnostic

## Evidence and decision

The board already classifies entries through canonical worktree identity, branch presence/terminal state and heartbeat. Its admission comparison skips an entry with any invalid/terminal status; therefore a `branch-path-mismatch` does not establish an active claim. The observed #81 mismatch and successful independent #87 materialization are consistent with that design.

The safe change is not a global bypass. It codifies a three-way distinction:

1. a valid active entry with a proven concrete path may block admission with `WAIT`;
2. a degraded or terminal entry is reported for owner recovery but contributes no blocking claim;
3. malformed global coordination state that cannot be read or locked remains a real lifecycle error and stays fail-closed.

## Lifecycle behavior

Before creating or admitting the new task, the lifecycle may run hygiene diagnostics. A non-zero board doctor result for a sibling mismatch is carried as a bounded warning, not converted into a global start failure. The start command must still expose the terminal result unambiguously: successful worktree/materialization, `WAIT` due to a valid concrete claim, or a genuine blocked error.

The board doctor continues to remove only entries it can prove obsolete under its existing identity/cleanliness rules. It must not "fix" a branch/path mismatch merely to unblock another task. The new task's admission continues under the board lock, and it must not read the malformed sibling's worktree as a factual claim.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| An actually active sibling is malformed and changes the same file. | A malformed record never becomes an assertion of safety; repair remains owner-scoped. Valid claims still block, and the change adds no automatic mutation or overlap acknowledgment. |
| A broad relaxation lets two valid tasks write one file. | Preserve atomic admission and add a same-file `WAIT` regression alongside independent-start cases. |
| Hiding warnings leaves recovery debt unnoticed. | Keep bounded hygiene warning with its board id/category and clearly print the start outcome. |
| A new behavior works only in this repository. | Modify the Copier template/source contract and prove fresh-render plus Copier-update behavior. |
| Rollout causes unmanaged cross-project writes. | Release only through an immutable tag and managed rollout PRs; downstream merge remains review-governed. |

## Verification

Use isolated multi-worktree fixtures to prove: a branch/path mismatch is diagnostic-only and untouched; a terminal sibling is diagnostic-only; an independent managed start materializes once; a valid same-file claim produces `WAIT`; unreadable/lock-failing board state remains fail-closed. Run lifecycle/unit tests, strict OpenSpec validation, fresh-render and Copier-update smoke tests, plus semantic OpenSpec verification.
