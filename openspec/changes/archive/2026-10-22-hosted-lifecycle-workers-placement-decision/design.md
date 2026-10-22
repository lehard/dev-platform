## Context

The hosted review worker is enabled (`DEV_PLATFORM_HOSTED_KINDS=review`), its first manual run passed every preflight check and reported `idle` (run 38221555792), and the previous slice makes it start automatically. What remains is evidence from real jobs.

## Decisions

1. **Evidence, not mechanism.** The change edits the engineering document and fixes defects that observation exposes.
2. **Observe, do not stage.** Evidence comes from real PRs' claim/result comments, job summaries, run durations and queue outcomes, never from a synthetic job that bypasses the lifecycle.
3. **Truthful limits.** A value that cannot be observed (for example per-job provider cost) is recorded as unobserved with the reason; nothing is estimated and presented as measured.
4. **Decision per kind.** Hosted only where the preflight passed and a real job was carried; otherwise the kind stays on the local operator node with the limitation as the BR-433 basis. The local fallback is compared by the same constraint list and gains no merge authority.
5. **`finalize` only by owner decision.** It runs candidate code beside a contents-write token; it is evaluated only after the owner enables it.

## Risks and mitigations

- Little PR traffic: the change waits visibly (board status) and a short observation window is stated in the record; no hosted claim is faked.
- Provider rate limit or outage during observation: recorded as the observed failure behavior, not retried around.
