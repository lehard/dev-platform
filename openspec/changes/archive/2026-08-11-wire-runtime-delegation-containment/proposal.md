# Change: Wire delegated-write containment into supported runtime execution

## Why

The archived `contain-delegated-write-scope` change added a useful containment helper and a durable contract, but the helper is not yet a supported end-to-end delegation path: no platform entrypoint currently guarantees that every write-capable delegated process is wrapped by the pre/post check, and downstream consumers on the latest published platform release do not yet receive it.

There is also a correctness gap in the current snapshot model. It records `HEAD` plus porcelain status entries. If `integration/main` already contains a modified path and a delegated writer changes the contents of that same path while leaving its porcelain status code unchanged (for example ` M file.py` before and after), the current set comparison can incorrectly classify the path as unchanged pre-existing state. A containment system must be content-aware for already-dirty paths, not status-code-aware only.

Finally, runtime capabilities are asymmetric. Platform-controlled Codex execution can use a real OS-level writable-root sandbox. Claude Code exposes pre-tool hooks but no universal native filesystem jail, especially for arbitrary shell commands. The platform must wire the strongest available enforcement, state the remaining boundary truthfully, and fail closed where detection-only execution could endanger unrelated dirty integration state.

## What changes

- Introduce one supported platform entrypoint/guard for write-capable delegated work. It validates an absolute registered `assigned_worktree`, captures pre-state, launches or wraps the delegated runtime in that worktree, and always performs the post-state check in a `finally`-equivalent path before reporting success.
- Strengthen `GitSnapshot` (or its replacement) so it fingerprints the actual state of dirty tracked files, index state, symlinks, and untracked paths sufficiently to detect content changes even when porcelain status remains the same.
- For platform-controlled Codex delegation, require the supported OS sandbox/write-root policy to restrict writes to `assigned_worktree`; fail before launch if the requested hard-containment policy cannot be established.
- For Claude Code, wire the supported pre-write hook mechanism for structured write tools where the platform controls the session/child configuration. Do not claim arbitrary shell hard containment unless an OS-level sandbox is actually active.
- Detection-only write delegation (a runtime/tool path without a proven hard filesystem boundary) SHALL NOT start while the integration checkout is already dirty. This avoids exposing another agent's uncommitted integration state to a writer that can only be caught after the fact.
- Always keep the post-delegation content-aware comparison even when hard prevention exists, so configuration regressions and integration `HEAD` movement are detected and recorded.
- Update agent-facing workflow guidance so supported platform-managed write delegation uses the guarded entrypoint; direct native write-capable subagent invocation outside that path is not represented as platform-contained.
- Render/update the change into managed consumers and perform a real downstream acceptance exercise before declaring runtime containment complete.

## Scope

This affects both fresh projects and existing managed projects that use platform-owned multi-agent capabilities and enable Claude and/or Codex tooling. It does not vendor OpenSpec-generated Claude/Codex skills. Project-owned harnesses may opt into the reusable helper/entrypoint but remain responsible for their own delegation implementation unless explicitly adopted.

## Compatibility risks

- Content-aware fingerprints must avoid destructive reads and remain practical on repositories with many untracked files.
- Claude hard-prevention capability must not be overstated; shell behavior may remain detection-only unless a real sandbox is present.
- Detection-only mode becoming unavailable on a dirty integration checkout is intentionally stricter and may expose existing workflow misuse that previously proceeded unsafely.
- Runtime command-line/sandbox interfaces can evolve; adapters must fail closed when the expected enforcement capability cannot be proven rather than silently falling back to weaker behavior while still claiming hard containment.

## Success criteria

A supported write-capable delegated task cannot be reported successful unless its assigned worktree was validated, the strongest supported runtime containment was applied, and the content-aware post-check completed. Changes to already-dirty integration files are detected even when Git status codes do not change. Detection-only delegation refuses to start over dirty integration state. At least one real managed consumer demonstrates the guarded path end-to-end before the change is archived.