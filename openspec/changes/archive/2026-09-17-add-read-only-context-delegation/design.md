# Design: Soft provider-local context shunting

## Decisions

1. **Micro-routing is separate from task routing.** R2/R3 remains the managed-task execution decision. Context delegation is an auxiliary read-only operation inside that execution.
2. **Reuse the routine profile.** The context worker resolves through current provider-local routing configuration. No new durable model identity or cross-provider selector is introduced.
3. **Question-directed input.** A delegation receives an explicit question and bounded repository paths/ranges. It is not an open-ended autonomous repository crawl.
4. **Structured evidence output.** The worker returns relevant path, symbol or range when available, finding, uncertainty, and a concise synthesis. The parent may perform targeted direct reads when exact source is subsequently needed.
5. **Read-only means read-only.** The supported worker path must not grant repository write capability. Read-only delegation does not inherit write-containment ceremony merely for symmetry.
6. **Soft first.** V1 provides an advisory/preferred path only. No PreToolUse hook, tool proxy, line-count block or other hard interception is enabled before calibration.
7. **Fail open truthfully.** Unsupported runtime capability, worker failure or materially low-confidence evidence returns an explicit fallback to direct reading; a failed or unlaunched worker is never recorded as a successful delegation.
8. **Evidence stays bounded.** Reuse the existing execution/routing provenance lifecycle. Do not create a trace service or store full prompts, transcripts or source contents.
9. **Payload evidence is not token evidence.** Deterministic line/byte volumes may measure context payload reduction. Token/request values are canonical only when a supported runtime emits the exact field; otherwise they remain unknown.
10. **Dogfood before rollout.** Central dev-platform may opt in first. This task does not enable hard enforcement downstream.

## Observation model

Each completed or attempted context delegation records enough local evidence for later calibration:

- provider/profile/model provenance when truthfully known;
- source file identity and deterministic source lines/bytes;
- returned evidence lines/bytes;
- later direct follow-up/re-read lines/bytes attributable to the same delegation when observable;
- elapsed time;
- completed, fallback, low-confidence or runtime-unavailable outcome;
- exact canonical usage only when supported, otherwise unknown.

The representation should support aggregation across managed runs without becoming a transcript store.
