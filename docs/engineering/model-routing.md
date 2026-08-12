# Provider-local model routing and delegated containment (central repository)

Detailed routing and delegation mechanics for `dev-platform` itself. `AGENTS.md` states the always-on invariant — routing is a required gate, the user does not choose an executor, and a delegation is claimed only when containment is proven. This document states how.

Concrete provider-local models are the replaceable `[model_routing]` policy in `.dev-platform.toml`, never a managed task artifact.

## Routing preflight

For every managed dev-platform task, the strong parent/supervisor performs a bounded semantic preflight immediately after the canonical OpenSpec is materialized and before implementation. It assesses uncertainty, cross-cutting impact, failure cost, verification difficulty, current-spec conflicts and material unknowns; it does not classify solely by expected diff size. The concrete strong parent is provider-local: Sol for the Codex entrypoint, Opus for the Claude Code entrypoint, both driven by the current `[model_routing]` policy.

This is a required dogfood execution gate, not an optional follow-up.

## Codex entrypoint

After the preflight, the Sol supervisor runs the following from the assigned task worktree:

```bash
python3 scripts/dogfood_task.py route-codex --profile <routine|standard|complex> --rationale "..." --evidence "..."
```

The command records the decision through `scripts/model_routing.py`. `routine` and `standard` immediately launch the configured lower-cost Codex executor through native `workspace-write` containment, while `complex` records the route and remains on Sol without a cheap-model attempt.

The child path is truthful: if native Codex containment cannot be proven, it reports that limit and the parent retains the work rather than claiming a delegation.

## Claude Code entrypoint

When work is entered through Claude Code instead, the supervisor runs:

```bash
python3 scripts/dogfood_task.py route-claude --profile <routine|standard|complex> --rationale "..." --evidence "..."
```

`complex` records the route and remains on the strong Claude parent (Opus, per the configured `[model_routing.claude]` complex profile) without a mandatory cheap-model attempt.

`routine`/`standard` record the route, refuse to proceed if the integration checkout is already dirty, and print the exact native Agent-tool call the supervisor must then actually invoke in place (no `isolation`, since the current working directory already is the assigned task worktree) — a Claude subagent can only be launched by the supervisor's own tool call, not spawned as a subprocess the way Codex is. The supervisor reviews the returned diff, then runs `python3 scripts/model_routing.py record-claude-execution --agent-id "<id>"` (or `dogfood_task.py report-claude-execution`), which runs the mandatory containment post-check and records execution evidence.

`finish`'s routing gate rejects a routine/standard Claude route that has no recorded, clean execution evidence — a route cannot be merely recorded without the child actually having run.

## Review and escalation

The parent reviews the returned diff and required checks in the task worktree. Routine/standard work must escalate with `scripts/model_routing.py escalate --reason "..."` on a material OpenSpec/current-spec conflict, substantial unexpected scope or cross-cutting impact, low confidence, or repeated substantive verification failure. Escalation preserves the canonical OpenSpec, current worktree/diff, findings and check evidence; do not restart useful work or enter an unbounded cheap-model retry loop.

## Delegated write containment

Platform-controlled write-capable delegation is platform-contained only with a valid assigned worktree, a proven native or fallback write boundary, and a content-aware post-check against the integration copy. `scripts/delegated_write_guard.py` remains the compatibility/post-check helper: a proven Codex `workspace-write` sandbox is the primary prevention layer, not a second custom guard. For unsupported or unprovable native modes, retain work on the parent or use the smallest supported guarded fallback. For Codex, system temp roots such as `/tmp` and `$TMPDIR` are checked with realpath semantics; unsafe topology downgrades to detection-only, or fails before launch when hard containment is required.

Native Claude Code subagents execute in place in the assigned task worktree, not through `isolation: worktree`: that mechanism forks a fresh worktree off the platform's main branch and cannot see the materialized-but-uncommitted managed OpenSpec/task state a routing preflight hands off, and settings-driven native sandboxing does not apply live to a subagent spawned mid-session. The invariant that governs a delegation is containment, not the specific child-worktree mechanism.

The supervisor records the integration pre-snapshot, refuses to start a detection-only child while the integration checkout is already dirty, and runs the required post-check after the child returns. A detection-only writer (no proven OS sandbox or hook boundary, for example shell-capable Claude delegation) must not start while the integration checkout is already dirty. No containment path stashes, resets, cleans, or deletes integration state.
