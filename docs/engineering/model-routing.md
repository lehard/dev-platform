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

The child path is truthful: if native Codex containment cannot be proven, it reports that limit and the parent retains the work rather than claiming a delegation. A local single-writer receipt and advisory lock are held for the exact assigned worktree throughout a launched Codex writer's lifecycle. A second writer is refused while that writer is live, and a stale or incomplete receipt fails closed rather than assuming the earlier writer disappeared.

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

The supervisor records the integration pre-snapshot, refuses to start a detection-only child while the integration checkout is already dirty, and runs the required post-check after the child returns. A detection-only writer (no proven OS sandbox or hook boundary, for example shell-capable Claude delegation) must not start while the integration checkout is already dirty. No containment path stashes, resets, cleans, or deletes integration state. After a launched Codex writer times out, is cancelled, encounters stream failure, or otherwise returns abnormally, the launcher terminates and reaps its process group before releasing ownership; if absence cannot be proven, the retained receipt blocks any later writer for that worktree.

## Execution provenance

The routing record (`.claude/model-routing/<change>.json`) is also the platform's bounded execution-provenance record; there is no separate tracing/observability system. `prepare` writes a `supervisor` field (role, provider, policy-selected model) for the strong parent recording the route. Once a child actually launches -- never merely prepared -- `run_codex`/`record_claude_execution` attach an `execution.participant` object: role (`executor`), provider, profile, model, reasoning effort and a bounded execution identifier.

Every model/effort value carries a `source`: `selected` (platform-chosen, passed to the runtime, not independently confirmed), `runtime-confirmed` (the runtime itself returned it for that execution), or `unknown`. Free-form model self-identification is never authoritative. Verified against the currently supported runtimes:

- **Codex**: `codex exec --json` emits a `thread.started` event carrying a real `thread_id`, which is recorded as the executor's bounded execution identifier (`kind: "codex-thread"`). No documented surface confirms the effective model or reasoning effort actually applied to a turn, so both stay `selected`/`unknown` respectively -- never upgraded to `runtime-confirmed`.
- **Claude Code**: after the supervisor invokes the native Agent-tool hand-off and it returns, `record-claude-execution --agent-id "<id>"` records that id as the executor's bounded execution identifier (`kind: "claude-agent-id"`). The Agent tool's current parameters are `description`, `isolation`, `model`, `prompt`, `run_in_background`, `subagent_type` -- there is no `effort` parameter, so a Claude child's reasoning effort is always recorded as `unknown`, never fabricated as selected.

A route that was only prepared -- containment unprovable, integration dirty, or the supervisor never actually invoked the hand-off -- has no `execution.participant`. Fallback (parent retains the work) and escalation both preserve the actual path that ran, not the preferred path that was requested.

For Codex, `execution.outcome` is `completed`, `failed`, or `abnormal`; an abnormal result records the cleanup/ownership state and error text and remains a failed route even when containment itself was clean. It is never presented as a clean handoff merely because the parent launcher returned.

`python3 scripts/agent_friction.py record --participant-role <supervisor|executor|unknown>` links a finding to the current run. The caller only asserts *which* participant a finding concerns; the identity itself is read back from this routing record, not self-reported. `unknown` (the default) is correct whenever attribution is genuinely ambiguous -- do not guess. Routed public GitHub evidence includes only a bounded `provider`/`model`/`source` line; execution identifiers and other machine-local detail stay in the local friction log. Friction deduplication (`fingerprint_for`) never includes model/provider -- the fingerprint identifies the underlying process problem, and provenance is per-occurrence metadata layered on top, so the same recurring issue across different models still updates one issue instead of splitting by model.

## Execution-efficiency baseline

The existing ignored routing record is retained under the integration checkout's `.claude/model-routing/` lifecycle directory (not only inside a disposable task worktree), and carries bounded efficiency evidence; there is no separate telemetry service or transcript store. A Codex launch attempt records platform-controlled start/end timestamps and monotonic elapsed milliseconds under `execution.efficiency.timing`. That timing is retained for launched, failed, abnormal, and launcher-boundary-unavailable attempts; the report counts only launched executions as baseline observations.

Optional canonical usage measurements are normalized as `{value, source, status}`. `status: measured` is used only for a structured runtime event with an exact supported field; unavailable, partial, malformed, or ambiguous multi-completion usage is `{value: null, source: unknown, status: unknown}`, never zero. `model_request_count` is a cross-runtime metric only when an adapter contract proves that one counted event is exactly one model request. The locally inspected Codex CLI (`0.146.1`) does not prove that identity: structured `turn.started` is retained as the runtime-local `codex_turn_started` counter, not a model-request value. Claude Code exposes neither a canonical request count nor execution duration. Token fields and runtime-local counters are compared only inside a compatible runtime/provider generation; platform-owned `elapsed_ms` and a future proven `model_request_count` are the only cross-runtime fields, still subject to task-family coverage.

Generate the local, read-only report from any task worktree:

```bash
python3 scripts/model_routing.py efficiency-baseline
```

The report scans local routing records across registered worktrees, preserves historical records without efficiency fields as missing evidence, counts completed/failed/abnormal outcomes and escalated routes already owned by routing provenance, and reads the existing active/archived OpenSpec verification receipt from the integration-owned lifecycle (so task-worktree cleanup does not erase verification evidence). It reports launched, verified/eligible and missing-verification observations separately; `sufficient` requires at least 15 verified managed executions plus a canonical comparable field measured across that eligible sample. It reports coverage, runtime-local counters and legacy ambiguous `request_count` values separately rather than silently mixing them. Medians plus p95 appear only when a populated metric has at least five observations. This report informs later routing calibration or external-runtime comparisons only; it does not switch models, alter tiers, impose budgets, or cancel work.

## Routing calibration

```bash
python3 scripts/model_routing.py routing-calibration
```

A bounded, read-only calibration view of the `R2`/`R3` rubric built from the same routing records and OpenSpec verification receipts as the efficiency baseline -- not a second execution store. It is stricter than the efficiency baseline on the routing facts a rubric review needs (an authored tier, a determinable actual path, a passed verification receipt) and does not require token/request comparability. A `usable` observation is a launched, verification-passed execution whose authored tier is known; `adequacy` is `insufficient` below 15 usable observations, and the report is still valid in that state.

The report separates the authored route from what actually ran: authored tier distribution and frontier exposure, verified `R2` success without `R3` escalation, `R2`->`R3` escalation counts with recorded reasons (`unknown` when the record has none) and success-after-escalation, direct-`R3` records, and `completed`/`failed`/`abnormal`/`unknown`/`not_launched` outcomes kept distinct. First-pass-vs-retry and human-intervention signals are reported as unavailable because no current record field proves them. Breakdowns by `task_family`, `rubric_version` and provider/model generation each carry their own count and `adequacy`. A successful direct `R3` execution is never labelled over-routing and never treated as evidence that `R2` would have failed.

`advice.candidate_decision` is a human-readable suggestion only -- `insufficient evidence / no policy change`, `no change`, `no confident change; monitor`, or a `review:` note pointing at frequent recorded escalations. `advice.requires_separate_managed_change` is always true: this command never edits `start_tier_routing.py`, `.dev-platform.toml`, the rubric or the model mapping, never creates a Development Backlog task, and never introduces a learned router.
