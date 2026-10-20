## Why
Claude delegation today is the supervisor's native Agent-tool call in place in the task worktree: no OS boundary, a self-reported launch and false containment violations when a sibling session moves integration `main`. With the sandboxed writer launch primitive the platform can start the Claude child itself, observe it and keep it out of the integration checkout physically.

## What Changes
- Add an explicit sandboxed Claude dispatch for a `delegated-child` Claude plan (`python3 scripts/model_routing.py dispatch-claude-sandboxed --prompt ...`). It requires a prepared Claude route with no delegation or execution and unchanged task content.
- Build a disposable copy of the assigned task worktree at its HEAD plus its current uncommitted task state (including the materialized OpenSpec package), using the existing disposable-checkout helper, with the uncommitted task state committed by the harness as a baseline before the writer starts; run `claude -p --permission-mode dontAsk --allowedTools Read,Grep,Glob,Edit,Write,Bash --output-format json` with the route's executor model through the sandboxed writer launch.
- Open the delegation with `launch_evidence: platform-observed` only after the process started; close it with the outcome.
- Return the result as a patch: the harness imports the writer files into its own staging clone, applies the existing write rules (no workflow or lifecycle-evidence paths), stores the patch beside the task-local routing record and applies it to the assigned task worktree only when task content still equals the route pre-snapshot; otherwise it refuses and keeps the patch.
- Record `execution` with `mechanism: sandbox-runtime`, tier `hard`, executed `participant` (executor, claude, profile, model, unknown effort, bounded id from the JSON result when present) and efficiency timing; reports count it as launched.
- The terminal routing gate accepts a completed platform-observed sandboxed Claude execution without the detection-only integration postcheck; the native self-reported path keeps its current checks.
- Document the command and its macOS-only HARD claim in `docs/engineering/model-routing.md`.

## Success Evidence
- Tests with a fake writer prove: delegation opens only after launch; patch applied only with unchanged pre-snapshot; forbidden paths rejected; integration movement during the run is not a violation; execution carries participant and platform-observed evidence; gate accepts it; token absent from routing record; non-macOS refusal.
- Full test groups and OpenSpec checks pass.

## Non-goals
Default route switch, removing native Agent-tool or detection-only code, negative probes with a real writer, DEC-0003, Linux.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `model-routing`: platform-observed sandboxed Claude execution.
- `platform-delegation`: OS-sandboxed disposable-copy containment for Claude.

## Impact
`template/scripts/model_routing.py`, `template/scripts/lifecycle_workers.py` (`run_in_session` launch callback; helpers reused), tests, `docs/engineering/model-routing.md`.
