## Why

Source backlog issue: `lehard/development-backlog#6`
Prepared against: `lehard/dev-platform@21a10c6dc41365fba80e1759dbfe89b3a99a67ea`

Live acceptance of `wire-runtime-delegation-containment` exposed a mismatch between the platform's `HARD` label and Codex `workspace-write` sandbox semantics. The runtime can additionally permit writes under system temporary roots such as `/tmp`/`$TMPDIR`, even when the assigned repository worktree is elsewhere. The existing content-aware post-check still catches protected integration mutations, but the current hard-tier description can overstate the actual writable boundary.

## What Changes

- Make Codex hard-tier classification topology-aware instead of assuming `workspace-write` means “only assigned_worktree is writable”.
- Model runtime-known extra writable temp roots and compare them against protected repository paths after normalization/realpath resolution.
- Fail closed when `require_hard=True` but the repository topology overlaps an unavoidable runtime-writable temp root.
- Otherwise downgrade honestly to `DETECTION_ONLY` with existing stricter preconditions rather than retaining a misleading `HARD` label.
- Keep the content-aware post-check as defense in depth for all tiers.
- Update the platform-delegation contract/tests/guidance without redesigning Codex sandboxing, Claude containment, publication, rollout, friction routing or managed-task flow.

## Capabilities

### Modified Capabilities

- `platform-delegation`: refine the definition and detection of hard Codex containment so the claimed enforcement tier matches the proven runtime writable surface for the current filesystem topology.
