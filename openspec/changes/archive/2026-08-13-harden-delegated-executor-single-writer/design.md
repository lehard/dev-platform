# Design: Single writer per assigned worktree

## 1. Writer ownership

The existing routed execution path remains authoritative. It gains a bounded writer-ownership record keyed by the exact assigned worktree and current routed launch identity. Only one live write-capable Codex launch may own that worktree at a time.

## 2. Process-tree lifecycle

The launcher must distinguish never-started, running, normally exited and abnormally terminated execution. Once a child is launched, timeout, cancellation, streaming failure or other abnormal return must trigger bounded termination/reaping of the relevant process tree before ownership is released.

## 3. Fail closed on ambiguity

A second launch is refused while ownership says the prior writer is active or while liveness cannot be disproved safely. The platform must not infer that a non-zero parent result means the child is gone.

## 4. Truthful provenance

Execution provenance records only what is known. A handoff cannot be represented as cleanly completed if the writer lifecycle is ambiguous or an orphan remains.

## 5. Safety boundaries

No new distributed service or cross-machine lock is introduced. Existing native sandbox/worktree containment and content-aware post-checks remain independent defense layers.
