## Why

`record_claude_execution` accepts any non-empty `agent_id` and persists `launched: true` plus an executor `participant` carrying the routing-selected model. The platform cannot independently confirm that a native Claude Agent-tool child actually ran: the Agent tool is invoked by the supervisor itself and returns no platform-verifiable receipt. A self-reported record therefore looks like hard execution evidence to the routing gate, friction attribution, the efficiency baseline and routing calibration.

## What Changes

- `record-claude-execution` records an explicit `outcome: "claimed"` with `launch_evidence: "self-reported"`, `launched: null` (unknown) and the supplied id only as `claimed_agent_id`. It no longer attaches an executed `participant`; the selected model is kept as a `claimed_participant` whose source is `self-reported`.
- The terminal routing gate accepts a routine/standard Claude route only through that explicit claimed outcome with a clean containment postcheck (the part the platform can actually verify), or through the unchanged retained path. It no longer relies on `launched` for Claude, and a legacy Claude record carrying `launched: true` without a claimed outcome is refused with a re-record diagnostic.
- Efficiency baseline and routing calibration treat self-reported Claude records (new and legacy) as not launched, labelled `claimed`, so they are never counted as verified executions.
- Codex subprocess evidence, retained execution, R1/R2/R3 policy and model selection are unchanged. No telemetry backend, provider abstraction or verification subsystem is added.

## Impact

`template/scripts/model_routing.py`, its tests, and the routing documentation (central and template). Downstream projects receive the same truthful semantics through normal release rollout; existing CLI flags (`--agent-id`, `report-claude-execution`) stay compatible.
