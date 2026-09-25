## Runtime receipt check

Before choosing a representation, the supported Claude Code surfaces were checked for an existing machine-verifiable execution receipt. The native Agent tool is invoked by the supervisor's own tool call and its result reaches only the supervisor's conversation; no platform-owned process observes it. Local transcript files are an undocumented internal format written under the same principal that would be making the claim, so they cannot independently prove a launch. No supported receipt exists, so the id stays a claim and unknown remains unknown.

## Representation

`record_claude_execution` writes:

- `outcome: "claimed"`, `launch_evidence: "self-reported"`, `launched: null`;
- `claimed_agent_id` (the supplied, bounded id), `summary`, tier/mechanism, `postcheck`, `recorded_at`;
- `claimed_participant` with provider/profile/model where model `source` is `self-reported` and effort is `unknown`.

It does not write `participant`, so friction executor attribution resolves to no participant rather than an unconfirmed one. The CLI keeps `--agent-id` and still requires a non-empty value so the claim stays traceable.

## Gate

For a Claude non-retained execution, the gate requires `outcome == "claimed"`, `launch_evidence == "self-reported"` and a clean postcheck. That makes terminal completion depend only on verifiable containment and an explicit, honestly-labelled claim. A legacy record (`launched: true`, no claimed outcome) is refused; because the route is still active before archive, rerunning `record-claude-execution` repairs it. Codex and retained branches are untouched.

## Reports

A small helper classifies an execution as self-reported Claude when it has `launch_evidence == "self-reported"` or a legacy `agent_id` without a platform launch outcome. The efficiency baseline and calibration use a `_launch_confirmed` helper instead of raw `launched`, and the calibration outcome label reports `claimed` for such records. Codex records are classified exactly as before.
