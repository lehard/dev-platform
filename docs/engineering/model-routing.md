# Provider-local model routing and delegated containment (central repository)

Detailed routing and delegation mechanics for `dev-platform` itself. `AGENTS.md` states the always-on invariant — routing is a required gate, the user does not choose an executor, and a delegation is claimed only when containment is proven. This document states how.

Concrete provider-local models are the replaceable `[model_routing]` policy in `.dev-platform.toml`, never a managed task artifact.

## Start-tier authoring (`R1`/`R2`/`R3`)

The routing decision is made twice, at two different times, for two different reasons:

- **Authoring time** (`scripts/managed_task.py create --bundle ...`) records a provider-neutral **recommended start tier** after the normal bounded targeted repository inspection that already happens while a managed task is prepared. This is the durable, human-facing recommendation: it has no concrete model ID, and it is exposed as an `[R2]`/`[R3]` prefix on the Development Backlog Issue title.
- **Execution time** (`route-codex`/`route-claude`, below) performs a bounded **freshness check** that confirms the authored tier still holds against the current repository, or escalates on newly discovered evidence. It is not a second full semantic assessment.

`start_tier_routing.py` defines the rubric:

- `R2` is the **default** production tier for ordinary, well-specified work — including work with a large diff, many files, high public visibility or high failure cost, as long as the intended behavior is clear and objectively verifiable. Diff size, file count, blast radius and failure cost alone never require `R3`; they may instead raise `assurance` while execution stays at `R2`.
- `R3` requires a concrete recorded hard trigger from a bounded allow-list: `unresolved_architecture`, `unknown_diagnosis`, `weak_verification_high_consequence`, `novel_cross_system`, `trustworthy_escalation_history`, `prior_balanced_failure`. `managed_task.py create --strong-trigger <category>` records one; omitting it always recommends `R2`.
- `R1` economy semantics are reserved in the rubric (`tier_to_profile` maps it to `routine`) but are **not** an automatic/recommended outcome of authoring in this version — `recommend_start_tier` never returns `R1`, and using it for actual execution is refused until a later evidence-gated change enables it.

The authored recommendation is one abstract tier plus a small provider-neutral routing receipt (`rubric_version`, `task_family`, `routing_confidence`, `assurance`, `effort_hint`, `strong_trigger`) embedded in the managed package. Tier, reasoning effort and assurance are independent: a task can be `R2` with high effort/assurance without becoming `R3`. Mapping an abstract tier to a concrete provider-local model stays two steps — tier → profile (`start_tier_routing.tier_to_profile`, fixed in code) and profile → model (`.dev-platform.toml`'s `[model_routing]`, replaceable) — so the model lineup can change without touching any Issue or OpenSpec.

A managed package authored before this rubric existed simply carries no routing receipt; it stays importable, and execution falls back to requiring an explicit `--profile`.

## Execution-time freshness check

Immediately after the canonical OpenSpec is materialized and before implementation, the executor runs the routing command below. When the managed package carries an authored routing receipt, omitting `--profile` performs the freshness check: it maps the authored tier to a profile (`R2` → `standard`, `R3` → `complex`) and records that as a **confirmed** route without redoing a full semantic assessment. Passing `--profile` explicitly still works exactly as before (useful for a legacy package with no receipt, or for a deliberate override) and is recorded alongside whatever tier was authored, if any.

Confirming does **not** require a strong parent/supervisor session: a task authored `R2` can start directly on the configured balanced Codex/Claude model. A strong parent remains available and is still exactly how `R3`/`complex` work is retained or how a confirmed `R2` route later escalates — it is a supported path, not a mandatory entrypoint for every routing-enabled task.

This is a required dogfood execution gate, not an optional follow-up.

## Codex entrypoint

From the assigned task worktree:

```bash
python3 scripts/dogfood_task.py route-codex --rationale "..." --evidence "..."
# or, to override the authored tier or route a legacy/receipt-less package explicitly:
python3 scripts/dogfood_task.py route-codex --profile <routine|standard|complex> --rationale "..." --evidence "..."
```

The command records the decision through `scripts/model_routing.py`. `routine` and `standard` (whether derived from an authored `R2` tier or passed explicitly) immediately launch the configured lower-cost Codex executor through native `workspace-write` containment, while `complex` (derived from `R3`, or passed explicitly) records the route and remains on the current session without a cheap-model attempt.

The child path is truthful: if native Codex containment cannot be proven, it reports that limit and the parent retains the work rather than claiming a delegation.

## Claude Code entrypoint

When work is entered through Claude Code instead:

```bash
python3 scripts/dogfood_task.py route-claude --rationale "..." --evidence "..."
# or, to override the authored tier or route a legacy/receipt-less package explicitly:
python3 scripts/dogfood_task.py route-claude --profile <routine|standard|complex> --rationale "..." --evidence "..."
```

`complex` (derived from `R3`, or passed explicitly) records the route and remains on the current strong Claude session (Opus, per the configured `[model_routing.claude]` complex profile) without a mandatory cheap-model attempt.

`routine`/`standard` (derived from `R2`/`R1`, or passed explicitly) record the route, refuse to proceed if the integration checkout is already dirty, and print the exact native Agent-tool call the supervisor must then actually invoke in place (no `isolation`, since the current working directory already is the assigned task worktree) — a Claude subagent can only be launched by the supervisor's own tool call, not spawned as a subprocess the way Codex is. The supervisor reviews the returned diff, then runs `python3 scripts/model_routing.py record-claude-execution --agent-id "<id>"` (or `dogfood_task.py report-claude-execution`), which runs the mandatory containment post-check and records execution evidence.

`finish`'s routing gate rejects a routine/standard Claude route that has no recorded, clean execution evidence — a route cannot be merely recorded without the child actually having run.

## Review and escalation

The parent reviews the returned diff and required checks in the task worktree. Routine/standard work must escalate with `scripts/model_routing.py escalate --reason "..."` on a material OpenSpec/current-spec conflict, substantial unexpected scope or cross-cutting impact, low confidence, repeated substantive verification failure, or a freshness check that discovers a new hard trigger absent from the authored recommendation. Escalation preserves the canonical OpenSpec, current worktree/diff, findings and check evidence; do not restart useful work or enter an unbounded cheap-model retry loop. Downgrading a route below its authored tier is not supported in this version.

## Delegated write containment

Platform-controlled write-capable delegation is platform-contained only with a valid assigned worktree, a proven native or fallback write boundary, and a content-aware post-check against the integration copy. `scripts/delegated_write_guard.py` remains the compatibility/post-check helper: a proven Codex `workspace-write` sandbox is the primary prevention layer, not a second custom guard. For unsupported or unprovable native modes, retain work on the parent or use the smallest supported guarded fallback. For Codex, system temp roots such as `/tmp` and `$TMPDIR` are checked with realpath semantics; unsafe topology downgrades to detection-only, or fails before launch when hard containment is required.

Native Claude Code subagents execute in place in the assigned task worktree, not through `isolation: worktree`: that mechanism forks a fresh worktree off the platform's main branch and cannot see the materialized-but-uncommitted managed OpenSpec/task state a routing preflight hands off, and settings-driven native sandboxing does not apply live to a subagent spawned mid-session. The invariant that governs a delegation is containment, not the specific child-worktree mechanism.

The supervisor records the integration pre-snapshot, refuses to start a detection-only child while the integration checkout is already dirty, and runs the required post-check after the child returns. A detection-only writer (no proven OS sandbox or hook boundary, for example shell-capable Claude delegation) must not start while the integration checkout is already dirty. No containment path stashes, resets, cleans, or deletes integration state.
