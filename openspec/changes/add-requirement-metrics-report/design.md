## Context

Requirement execution facts already exist in separate owners:

- **Requirement and children**: the Development Backlog Requirement Issue (created/closed time, `requirement-children` block parsed by `requirement_intake.parse_requirement_body`) and each linked `type:internal-change` child Issue (created/closed time, `**OpenSpec change:**` / managed package identity).
- **Pre-authoring**: machine-local `.claude/pre-authoring/requirement-<N>/` (`state.json` `created_at`, `selection.json` depth/routing, `add.json` unresolved choices and their recorded human answers, `intents.json`, handoff envelopes with `created_at`).
- **Managed provenance**: the archived change's `.managed-task.json` (`imported_at`, `routing_receipt` with `recommended_start_tier`, `task_family`, `assurance`).
- **Routing/execution provenance**: the integration-owned `.claude/model-routing/<change>.json` (`prepared_at`, `supervisor`, `execution` participant or self-reported `claimed_participant`, `outcome`, `escalations`, `execution.efficiency` timing/usage with `{value, source, status}`).
- **Verification**: archived `verification.md` and `automated-checks.json` (executed commands with durations and outcomes).
- **Independent review**: archived `independent-review-request.json`, `independent-reviews/<perspective>.json` (reviewer provider/model/source, `launched_at`/`completed_at`, `availability`, findings, `task_content_digest`, `request_id`) and `independent-review-dispositions.json`. Only the final round survives in the archive; earlier rounds survive only in the published PR commit history.
- **Publication and CI**: the child branch PR(s) (`agent/<change>`), their commits, `publication:*` label events, and GitHub Actions runs for that branch (workflow, head SHA, conclusion, `run_attempt`, `run_started_at`, `updated_at`).
- **Friction**: the local friction log (`[paths] friction_log`), whose events carry `task`, `branch`, `triggers`, `classification`, `category`.
- **Session signals**: Claude Code keeps local JSONL transcripts under `~/.claude/projects/<sanitized-path>/`, and each entry carries `type`, `timestamp`, `sessionId`, `gitBranch` and `cwd`. Assistant entries carry the runtime's per-request `usage`. The platform currently reads none of this.

`model_routing.py efficiency-baseline` and `routing-calibration` already provide read-only, advisory aggregates over routing records. The new report composes the same records rather than replacing those commands.

## Goals / Non-Goals

Goals: one read-only command for one Requirement and for a set of Requirements. Every value is traceable to an existing source. Unknown and lower-bound evidence stay explicit. Independent review cost becomes visible. The one fact that is lost today (reviewer runtime usage) is retained going forward.

Non-goals: score/index, persistence, new lifecycle step, policy automation, monetary cost, and fixing unrelated friction.

## Decisions

### 1. One read-only module, two subcommands, no persistence

`template/scripts/requirement_metrics.py` with a thin `scripts/requirement_metrics.py` wrapper (`source_adapter.run_template`):

```bash
python3 scripts/requirement_metrics.py report --requirement owner/repo#N [--format json|text] [--offline] [--claude-projects-dir DIR]
python3 scripts/requirement_metrics.py aggregate (--requirement owner/repo#N ... | --closed-since YYYY-MM-DD) [--format json|text] [--offline] [--claude-projects-dir DIR]
```

It prints to stdout only. It writes no file, cache, log, GitHub comment, label, Project field or git ref, and it does not fetch into the local repository. Remote reads go through `gh` (REST/GraphQL) with bounded calls per child. `--offline` skips every remote read, and those sections become `unknown` with reason `offline`. A remote failure makes only the affected section `unknown` with a bounded diagnostic. It never fails the whole report unless the Requirement Issue itself cannot be read. In that case the command exits non-zero with an actionable message. The command runs from the integration checkout or any task worktree and resolves the integration root the way existing reports do. Local sources are read from the integration root.

### 2. Value model: `{value, status, sources}`

Every metric leaf is:

```json
{"value": <number|string|null>, "status": "measured|derived|partial|unknown", "sources": ["<ref>", ...], "reason": "<only when not measured>"}
```

- `measured`: read directly from one source field (e.g. `run_started_at`, a report `launched_at`).
- `derived`: computed deterministically from measured inputs (a duration between two measured timestamps, a count over a complete source).
- `partial`: a lower bound or incomplete coverage (history reconstructed from published commits, some children unreadable, session attribution overlaps another Requirement).
- `unknown`: no trustworthy value. `value` is `null`, and `reason` says why (`source-missing`, `unreadable`, `unsupported-runtime`, `offline`, `historical-record-without-field`, …).

A sum or count over inputs that include an `unknown` input is `partial` when at least one input is known, and `unknown` when none is. It is never zero. Sources are compact refs: `file:<repo-relative path>@<git blob or sha256 prefix>`, `local:<path relative to integration .claude>` for machine-local files, `gh:issue:owner/repo#N`, `gh:pr:owner/repo#N@<head sha>`, `gh:commit:<sha>:<path>`, `gh:run:<run id>`, `claude-transcript:<session id>`. The report includes a top-level `sources` index and a `generated_at`/`head` identity. It carries no content payloads.

### 3. Report structure

```
requirement: ref, title, state, created_at, closed_at, children_count
cycle: total (created→closed, or created→now as partial while open), stages[] (name, at, source), stage_durations[]
children[]: ref, change, state, start_tier, task_family, assurance,
            routing: supervisor{provider, model{value,source}}, executor{provider, model{value,source}, launch_evidence, outcome}, escalations
            execution_efficiency: elapsed_ms and usage copied from the routing record as-is (runtime-local, with source/status)
            verification: receipt present/pass, method present
            validation: full_cycles (count, partial), per-cycle durations and outcome, total_duration
            review: (see 4)
            publication: prs[] (number, created_at, merged_at, state, commits), queue_blocked_events, publication_cycles
            ci: runs (count), by_workflow, distinct_heads (CI cycles), failed_runs, rerun_attempts, wall_time_total_s, cycles_after_first_review
            friction: count, by_trigger, by_classification, ids
totals: children, executions, escalations, review rounds/launches/wall time/findings/reruns by cause, full validations, CI runs/cycles/wall time, publication cycles, human stops, friction
human_stops: pre_authoring_decisions (answered ADD choices), review_blockers (dispositions with status blocker), project_blocked (unknown: no recorded history), session_interruptions (from 6, runtime-local)
session_quality: per runtime (see 6)
provider_usage: per provider/runtime group, never summed across runtimes
```

Stages are the observed timestamps that exist: `requirement_created`, `pre_authoring_started`, `depth_selected`, `handoff_prepared`, `child_created`, `child_imported`, `routed`, `execution_recorded`, `first_review_launched`, `last_review_completed`, `pr_created`, `pr_merged`, `child_closed`, `requirement_closed`. A missing stage is omitted from `stages` and listed under `missing_stages`. Durations are computed only between consecutive present stages.

Child resolution: children come from the Requirement's children block. The change name comes from the child Issue's `**OpenSpec change:**` line or the existing managed-package reader, whichever the codebase already uses for this purpose. The archive entry is matched by `.managed-task.json` `change`. The routing record is matched by `change` and verified against `source_issue` equal to the child ref. A mismatch or absence makes that section `unknown` rather than picking another record.

### 4. Independent review cost

For each child, read the review evidence at every published commit that touched it:

1. List the child PR's commits (`GET /repos/{o}/{r}/pulls/{n}/commits`, bounded to 250).
2. For commits whose tree changed the active or archived `independent-reviews/*.json` or `independent-review-request.json` (from per-commit `files`, bounded), read those files at that commit via the contents API.
3. Group reports into rounds by `request_id` in commit order. Add the archived final evidence as the last round if its `request_id` is new.

Per round: `request_id`, `perspectives` (per perspective: provider, model `{value, source}`, runtime, availability, launched_at, completed_at, wall_time_s, findings by severity), `launches` (reports whose reviewer launch was platform-observed and available, plus unavailable reports whose limitation is not a preflight/resolution failure; unknown when ambiguous), `wall_time_s` (max completed − min launched), `task_content_digest`, `runtime_usage` when present (see 5), and `cause`:

- `initial`: first round.
- `substantive-candidate-change`: `task_content_digest` differs from the previous round.
- `reviewer-unavailable`: same digest, and the previous round had any unavailable perspective.
- `process-rerun`: same digest, and the previous round was fully available (lifecycle-only commits, manual rerun, evidence repair).
- `unknown`: digest missing on either side.

Dispositions give `material_findings`, `rejected` and `blocker` counts. `rounds` status is `partial` because rounds that were never committed are invisible. `cycles_after_first_review` counts full-validation cycles and CI cycles (distinct PR head SHAs with a `Platform CI` run) that happened after the first round's `completed_at`, which exposes the downstream cost of reruns. The reviewer diff exclusion and acceptance rules are unchanged.

### 5. Reviewer runtime usage (forward instrumentation)

`independent_review_runner.run_perspective` adds an optional `runtime_usage` block to an available report, parsed only from the runtime's structured result that the runner already receives:

- Claude Code print JSON result: `usage.input_tokens`, `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens`, `usage.output_tokens`, `num_turns`, `duration_ms`, `duration_api_ms`.
- Codex `--json` events: exactly one `turn.completed` `usage` (`input_tokens`, `cached_input_tokens`, `output_tokens`), reusing the existing single-completion rule in `model_routing` (more than one completion → unknown).

Shape: `{"runtime": "<runtime>", "fields": {"<runtime field name>": {"value": int|null, "source": "runtime-confirmed"|"unknown", "status": "measured"|"unknown"}}}`. Field names stay runtime-local. They are not mapped into the canonical cross-runtime usage fields, because Claude and Codex count cached input differently. Monetary fields (`total_cost_usd`) are not retained. Absent, non-integer, negative or boolean values become unknown. A parse failure never makes a review unavailable. `_validate_report` accepts the optional block and validates its shape leniently for historical reports. The block does not participate in review freshness, task-content identity or disposition binding.

### 6. Counters-only Claude Code session adapter

Default directory `~/.claude/projects` (override `--claude-projects-dir`). The adapter considers only subdirectories whose name is the Claude Code sanitized form of the integration root or of a registered worktree path (prefix match on the sanitized integration root), plus their `*/subagents/*.jsonl` files. An unreadable directory makes the section `unknown` (`source-missing`/`unreadable`).

Attribution is exact, per entry:

- **Child**: the entry's `gitBranch` equals the child branch `agent/<change>`.
- **Requirement**: within one session file, the span from the first to the last entry whose user text or tool-use input contains the exact Requirement ref or an exact linked child ref (string match in memory only). Entries in that span are attributed. A span that also contains another Requirement's exact ref makes the counters `partial` (`shared-session`).

Counters over attributed entries, each `measured` or `derived` with the session ids as sources:

- `prompt_turns`: user entries with human text (not `isMeta`, not tool-result-only, not interruption markers).
- `interruptions`: user text entries that are the runtime's interruption marker (`[Request interrupted by user`).
- `tool_rejections`: tool results marked as a user rejection of a tool use.
- `tool_errors`: tool results with `is_error: true` that are not rejections.
- `reprompts_after_interrupt_or_rejection`: human prompts that directly follow an interruption or rejection.
- `session_time_s`: last minus first attributed timestamp per session, summed.
- `active_time_s`: sum of gaps between consecutive attributed entries, with each gap capped at 300 s.
- `runtime_usage`: assistant `message.usage` fields summed after de-duplicating by `requestId` (falling back to `message.id`). Runtime-local, `claude-code-transcript`.

Unrecognized entry shapes are skipped and counted in `unrecognized_entries`. If the format cannot be recognized at all, the section is `unknown` (`unsupported-format`). No text, tool input/output, file path content or prompt is ever copied into the output, only counts, durations, session ids and the attribution method. Codex and other runtimes: `{"status": "unknown", "reason": "unsupported-runtime"}`.

### 7. Aggregate

`aggregate` builds each Requirement's report, then emits:

- `rows`: one compact row per Requirement with the headline totals side by side (cycle time, children, executions, escalations, review rounds, reruns by cause, full validations, CI cycles, CI wall time, publication cycles, human stops, friction). The system trade-off stays visible without a composite score.
- `groups`: by `children_count`, `task_family` (the set over children) and `start_tier` (the set over children). Each group has `n`, and medians/p95 only when `n >= 5` (`EFFICIENCY_MIN_PERCENTILE_OBSERVATIONS`), otherwise `adequacy: insufficient`.
- `runtime_groups`: usage and session metrics keyed by `provider/runtime` (and reviewer runtime). Values are never summed or compared across keys.
- `advice`: a fixed note that the report is advisory and requires a separate managed change for any policy decision, mirroring routing calibration.

`--closed-since` selects closed `type:requirement` Issues carrying the checkout's configured `[development_backlog]` project label through one bounded search.

### 8. Privacy and ownership boundaries

The command reads only. Its output contains identifiers, timestamps, counts, durations, statuses and source refs. It never includes prompts, responses, transcript text, tool payloads, diffs, code, finding summaries/evidence text, friction observation/evidence prose, or rationale text. Friction events are reported as id, trigger, classification and category only. The template ships the command to downstream projects, where it uses the same sources and degrades to unknown where a source is absent.

### 9. Implementation clarifications

These refine the decisions above without changing their intent:

- **Rounds**: a perspective reported again under the same `request_id` with a different launch identity (`launch_id`, else `context_id`, else `launched_at`) starts a new round, because `run_review` reuses a still-current request for a rerun. The same report committed twice (for example moved into the archive) is one round.
- **Validation cycles**: each distinct published content of `automated-checks.json` is one cycle, timed by its commit date. A cycle is `full` when it executed `run_test_groups.py --all`.
- **Publication**: `publication_cycles` counts `publication:queued` label events and `queue_blocked_events` counts `publication:blocked` label events on the child PRs.
- **CI cycles** use the primary CI workflow: `Platform CI` centrally and `Dev Platform` in managed projects.
- **Offline children** come from the exact local Requirement integration receipts (`.claude/requirement-integration/requirement-<N>/*.json`) and the parent retrospective receipt, so `children_count` is `partial` (`offline`).
- **Stages** whose source has no timestamp (`selection.json`, a direct handoff) are listed under `missing_stages`. Present stages are ordered by their timestamps, so a regenerated source such as a later handoff envelope never produces a negative duration.
- **Dispositions**: an archived or active change with no disposition record has zero rejected and zero blocker dispositions.
- **Session attribution**: an exact reference is `owner/repo#N` or the Issue URL `https://github.com/owner/repo/issues/N`. Any other reference in the Requirement's Backlog repository inside a span marks it `shared-session`, because telling Requirements apart would need a remote read. This errs toward `partial`. No attributed entries at all is `unknown` (`no-attributed-sessions`), not zero.
- **Session counters**: subagent (sidechain) entries count toward tool counters, time and usage, but not toward `prompt_turns` or `interruptions`, because their prompts come from the parent agent. Runtime-generated user text (`promptSource: system`, or a leading `<task-notification>`/`<system-reminder>` style tag) is not a prompt turn. A tool rejection is the runtime's `toolDenialKind: user-rejected` or its rejection marker, and other denied or failed tool results count as tool errors.
- **Review report digest**: `runtime_usage` is written once as part of the immutable report, so the existing whole-report digest covers it. Disposition binding logic does not read or interpret the block.
- A Requirement Issue without the `type:requirement` label is refused with an actionable message.

## Risks / Trade-offs

- PR commit history reconstruction costs several API calls per child. It is bounded, and `--offline` keeps a fast local view.
- Claude transcript format is runtime-local and unversioned. Shape validation plus `unknown` avoids guessing, and the adapter is isolated so a format change breaks only this section.
- The reference-span attribution for supervisor sessions is a documented heuristic. Its method is stated in the output, and overlap is marked partial.
- Rounds and validation cycles that were never committed are invisible. The counts are labelled partial lower bounds.

## Verification

Unit tests with fake `gh` responses and temporary directories: value model (unknown never zero, partial propagation), child resolution mismatch → unknown, stage/cycle computation, review round reconstruction and each rerun cause, validation/CI cycle counting incl. cycles after the first review, friction filtering without prose, human stops, transcript adapter counters/dedup/attribution/overlap/unsupported format with an assertion that no transcript text appears in output, aggregate grouping and sample adequacy, runtime_usage parsing for Claude/Codex (valid, partial, malformed, multiple completions), and `_validate_report` accepting reports with and without the block. Dogfood: run `report` on an already completed Requirement and `aggregate` over at least two completed Requirements. Record in `verification.md` that the values trace to existing sources without manual input.
