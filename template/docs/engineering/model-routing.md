# Provider-local model routing

Managed work starts with a strong parent/supervisor. After `start_managed_task.py` materializes canonical OpenSpec in the task checkout, the parent performs a bounded semantic preflight and records the execution profile with `scripts/model_routing.py prepare`.

The profile is `routine`, `standard`, or `complex`. The user does not select the executor. The parent assesses uncertainty, blast radius, failure cost, verification difficulty, current-contract conflicts and material unknowns; a small expected diff is not enough to force a low-cost profile.

Concrete mappings are current runtime policy in `[model_routing]` in `.dev-platform.toml`, rather than data in a backlog issue or OpenSpec artifact. Update those mappings as provider model lineups change.

For Codex, `codex-argv` and `run-codex` require a proven native `workspace-write` sandbox for the assigned worktree. If that proof is unavailable, the tool reports the constraint and the parent retains the work or uses a separately reviewed fallback; it never claims delegation that did not occur.

For Claude Code, use `dispatch-claude` rather than the `isolation: worktree` Agent-tool option: that option forks a fresh worktree off the platform's main branch and cannot see the materialized-but-uncommitted managed OpenSpec/task state a routing preflight hands off. `dispatch-claude` records the route and, for `routine`/`standard`, refuses to start over a dirty integration checkout, then emits the exact in-place Agent-tool call for the supervisor to invoke -- no `isolation`, since the child shares the supervisor's own assigned task worktree directly. A Claude subagent can only be launched by the supervisor's own tool call, not spawned as a subprocess; after it returns, the supervisor runs `record-claude-execution --agent-id "<id>"`, which runs the mandatory `postcheck` and persists execution evidence, then reviews the child diff and executes the normal task checks. Because the child shares the supervisor's process rather than a proven OS write boundary, this path is detection-only: the pre/post content-aware integration check is the actual write boundary, not a defense-in-depth extra.

Routine or standard work must escalate to the complex profile when it finds a material OpenSpec/current-spec conflict, unexpected cross-cutting impact or scope, low confidence, or repeated substantive verification failures. Use `scripts/model_routing.py escalate --reason "..."`; the hand-off retains the canonical change, worktree/diff and evidence rather than restarting the task.
