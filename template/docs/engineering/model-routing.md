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

## Standard profile: parent-only routing in a standalone clone

The `standard` workflow profile has no linked worktree -- the supervisor's own isolated project clone is both the assigned task checkout and the integration copy. `prepare` detects this (task checkout resolves to the same path as `main_root()`) and records the route with `topology: "standalone-clone"` instead of requiring a distinct registered `git worktree`. This is what lets routing preflight run at all for `standard` (there is nothing else for it to point at); the record still truthfully identifies parent-only execution.

That exception never extends to a write-capable child: `dispatch-codex`, `dispatch-claude`, `run-codex`, `codex-argv` and `claude-agent` all refuse to launch on a `standalone-clone` route, because there is no distinct worktree to prove a containment boundary against. A `standard`-profile task keeps `routine`/`standard` work on the supervisor itself; only `multi-agent`'s linked worktrees can host an actual delegated child writer.

## Execution provenance

The routing record is also the bounded execution-provenance record; there is no separate tracing/observability system. `prepare` records a `supervisor` field for the strong parent; once a child actually launches (never merely prepared), the execution record gains a `participant` object with role, provider, profile, model, reasoning effort and a bounded execution identifier.

Every model/effort value carries a `source`: `selected` (platform-chosen, not independently confirmed), `runtime-confirmed` (the runtime itself returned it), or `unknown`. Free-form model self-identification is never authoritative -- verify what the current supported Codex/Claude Code runtime can actually confirm before claiming a value, and degrade to `unknown` rather than guess. A route that was only prepared, not actually executed, has no `participant`; fallback and escalation preserve the actual path that ran, not the preferred one.

`agent_friction.py record --participant-role <supervisor|executor|unknown>` links a finding to the current run: the caller asserts only *which* participant it concerns, and the identity is read back from this routing record rather than self-reported. Routed public GitHub evidence carries only a bounded provider/model/source line; execution identifiers and other machine-local detail stay local. Friction fingerprinting never includes model/provider -- it identifies the underlying process problem, with provenance layered on as per-occurrence metadata.

## Execution-efficiency baseline

The existing ignored routing record is retained under the integration checkout's `.claude/model-routing/` lifecycle directory (not only inside a disposable task worktree), and carries bounded efficiency evidence; there is no separate telemetry service or transcript store. A Codex launch attempt records platform-controlled start/end timestamps and monotonic elapsed milliseconds under `execution.efficiency.timing`. That timing is retained for launched, failed, abnormal, and launcher-boundary-unavailable attempts; the report counts only launched executions as baseline observations.

Optional canonical usage measurements are normalized as `{value, source, status}`. `status: measured` is used only for a structured runtime event with an exact supported field; unavailable, partial, malformed, or ambiguous multi-completion usage is `{value: null, source: unknown, status: unknown}`, never zero. `model_request_count` is a cross-runtime metric only when an adapter contract proves that one counted event is exactly one model request. The locally inspected Codex CLI (`0.146.1`) does not prove that identity: structured `turn.started` is retained as the runtime-local `codex_turn_started` counter, not a model-request value. Claude Code exposes neither a canonical request count nor execution duration. Token fields and runtime-local counters are compared only inside a compatible runtime/provider generation; platform-owned `elapsed_ms` and a future proven `model_request_count` are the only cross-runtime fields, still subject to task-family coverage.

Generate the local, read-only report from any task worktree:

```bash
python3 scripts/model_routing.py efficiency-baseline
```

The report scans local routing records across registered worktrees, preserves historical records without efficiency fields as missing evidence, counts completed/failed/abnormal outcomes and escalated routes already owned by routing provenance, and reads the existing active/archived OpenSpec verification receipt from the integration-owned lifecycle (so task-worktree cleanup does not erase verification evidence). It reports launched, verified/eligible and missing-verification observations separately; `sufficient` requires at least 15 verified managed executions plus a canonical comparable field measured across that eligible sample. It reports coverage, runtime-local counters and legacy ambiguous `request_count` values separately rather than silently mixing them. Medians plus p95 appear only when a populated metric has at least five observations. This report informs later routing calibration or external-runtime comparisons only; it does not switch models, alter tiers, impose budgets, or cancel work.
