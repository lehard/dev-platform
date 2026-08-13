# Provider-local model routing

Managed work starts with a strong parent/supervisor. After `start_managed_task.py` materializes canonical OpenSpec in the task checkout, the parent performs a bounded semantic preflight and records the execution profile with `scripts/model_routing.py prepare`.

The profile is `routine`, `standard`, or `complex`. The user does not select the executor. The parent assesses uncertainty, blast radius, failure cost, verification difficulty, current-contract conflicts and material unknowns; a small expected diff is not enough to force a low-cost profile.

Concrete mappings are current runtime policy in `[model_routing]` in `.dev-platform.toml`, rather than data in a backlog issue or OpenSpec artifact. Update those mappings as provider model lineups change.

For Codex, `codex-argv` and `run-codex` require a proven native `workspace-write` sandbox for the assigned worktree. If that proof is unavailable, the tool reports the constraint and the parent retains the work or uses a separately reviewed fallback; it never claims delegation that did not occur.

For Claude Code, use `dispatch-claude` rather than the `isolation: worktree` Agent-tool option: that option forks a fresh worktree off the platform's main branch and cannot see the materialized-but-uncommitted managed OpenSpec/task state a routing preflight hands off. `dispatch-claude` records the route and, for `routine`/`standard`, refuses to start over a dirty integration checkout, then emits the exact in-place Agent-tool call for the supervisor to invoke -- no `isolation`, since the child shares the supervisor's own assigned task worktree directly. A Claude subagent can only be launched by the supervisor's own tool call, not spawned as a subprocess; after it returns, the supervisor runs `record-claude-execution --agent-id "<id>"`, which runs the mandatory `postcheck` and persists execution evidence, then reviews the child diff and executes the normal task checks. Because the child shares the supervisor's process rather than a proven OS write boundary, this path is detection-only: the pre/post content-aware integration check is the actual write boundary, not a defense-in-depth extra.

Routine or standard work must escalate to the complex profile when it finds a material OpenSpec/current-spec conflict, unexpected cross-cutting impact or scope, low confidence, or repeated substantive verification failures. Use `scripts/model_routing.py escalate --reason "..."`; the hand-off retains the canonical change, worktree/diff and evidence rather than restarting the task.

## Delegated write containment

Platform-controlled write-capable delegation is platform-contained only with a valid assigned worktree, a proven native or fallback write boundary, and a content-aware post-check against the integration copy. `scripts/delegated_write_guard.py` remains the compatibility/post-check helper: a proven Codex `workspace-write` sandbox is the primary prevention layer, not a second custom guard. For unsupported or unprovable native modes, retain work on the parent or use the smallest supported guarded fallback. For Codex, system temp roots such as `/tmp` and `$TMPDIR` are checked with realpath semantics; unsafe topology downgrades to detection-only, or fails before launch when hard containment is required.

Native Claude Code subagents execute in place in the assigned task worktree, not through `isolation: worktree`. The invariant that governs a delegation is containment, not the specific child-worktree mechanism. The supervisor records the integration pre-snapshot, refuses to start a detection-only child while the integration checkout is already dirty, and runs the required post-check after the child returns. No containment path stashes, resets, cleans, or deletes integration state.

## Execution provenance

The routing record is also the bounded execution-provenance record; there is no separate tracing/observability system. `prepare` records a `supervisor` field for the strong parent; once a child actually launches (never merely prepared), the execution record gains a `participant` object with role, provider, profile, model, reasoning effort and a bounded execution identifier.

Every model/effort value carries a `source`: `selected` (platform-chosen, not independently confirmed), `runtime-confirmed` (the runtime itself returned it), or `unknown`. Free-form model self-identification is never authoritative -- verify what the current supported Codex/Claude Code runtime can actually confirm before claiming a value, and degrade to `unknown` rather than guess. A route that was only prepared, not actually executed, has no `participant`; fallback and escalation preserve the actual path that ran, not the preferred one.

`agent_friction.py record --participant-role <supervisor|executor|unknown>` links a finding to the current run: the caller asserts only *which* participant it concerns, and the identity is read back from this routing record rather than self-reported. Routed public GitHub evidence carries only a bounded provider/model/source line; execution identifiers and other machine-local detail stay local. Friction fingerprinting never includes model/provider -- it identifies the underlying process problem, with provenance layered on as per-occurrence metadata.
