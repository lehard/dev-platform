## Why

`finish` already calls the parent reconciliation after a confirmed merge, but a missing retrospective stops it without a retry command, several children make it return silently, and `status` never looks at the parent. The last delivery therefore closed its Requirement with a manual `advance`. Deferred worktree records pile up because only a manual command consumes them.

## What Changes

- `finish` is the normal place where a Requirement closes. After a confirmed merge it closes the parent when every child is terminal and the retrospective is current, and prints the result.
- A closure cannot fail to happen silently. Open children are named and `finish` succeeds for its own child. Anything else that prevents closure is a non-zero exit naming the cause, the fixing command and the retry.
- An Issue that is already closed is reported only as already closed; `finish` claims neither proof nor closure by this run.
- Before publishing a managed child, `finish` prints what closure would miss, without stopping publication.
- `status` of a delivered child reports an open parent.
- `finish` consumes the deferred worktree records of earlier tasks through the existing safety checks, naming each record.

## Non-goals

Hosted workers, a closure service, writing the retrospective in `finish`, making the retrospective a merge gate, removing `advance`, closing Requirements delivered only by quick PRs, release and rollout.
