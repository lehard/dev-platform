# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic OpenSpec review of completeness, correctness, and coherence, plus strict validation and automated platform checks.

## Completeness

- A Git-admin-backed, advisory single-writer lock and receipt are bound to the exact assigned worktree, so they do not dirty task contents.
- A second concurrent writer is refused; a malformed, live, or otherwise ambiguous stale receipt remains fail-closed.
- Every launched child starts in its own session/process group, enabling cleanup of descendants rather than only the immediate `Popen` leader.

## Correctness

- Normal completion releases ownership only after the group is absent. Timeout, cancellation, stream failure, and other abnormal returns terminate and reap the process group; unresolved cleanup retains an ambiguous receipt.
- `model_routing.py` persists `completed`, `failed`, or `abnormal` outcomes and fails the routing operation after an abnormal child outcome, so provenance cannot present it as a clean handoff.
- Focused regressions cover duplicate launch refusal, ambiguous stale state, silent streaming timeout, descendant cleanup, clean retry eligibility, and truthful abnormal routing provenance.

## Coherence

- Existing native Codex containment and the integration post-check remain in place; process ownership adds a separate lifecycle safeguard and performs no reset, stash, clean, or external scheduler action.
- Runtime receipt state is kept solely in Git administrative metadata, remains local to the assigned worktree, and does not create a new durable routing system.

Automated-Checks-Evidence: automated-checks.json
