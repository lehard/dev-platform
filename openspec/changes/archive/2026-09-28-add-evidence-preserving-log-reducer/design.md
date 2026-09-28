# Design: Compression may summarize; evidence must still prove

## Dependencies

This change depends on #131 so every reducible log has an exact preserved source and stable recall identity.

## Decisions

1. **Source is canonical.** The original execution log, command result and exit status remain authoritative.
2. **Structured receipt.** A receipt may contain command identity, exit/result status, selected error/warning facts, exact quotes/ranges, uncertainty and source handle/digest.
3. **Deterministic binding.** Receipt quotes/ranges and structured command/exit fields are checked against the preserved source. A model cannot self-attest its own summary.
4. **Deterministic extraction first.** Known structured log formats use parsers for reliable fields before any semantic model pass.
5. **Cheap reducer is optional.** Semantic reduction may use the configured routine provider-local profile, but failure/low confidence/unavailable runtime returns to exact source evidence.
6. **No verification shortcut.** Terminal or check pass/fail remains determined by canonical commands/checks and their source evidence, never by a reducer's prose.
7. **Bounded provenance.** Record reducer participant/profile where known, source/receipt size, verification outcome, fallback/recall volume and supported usage. No full transcript database.
8. **Deterministic first and smaller than hot.** When no semantic receipt is supplied, extract a bounded exact error/result line from supported command/test logs. Publish either kind of receipt only when its serialized bytes are smaller than both the source and the existing hot excerpt. Bind the source digest recorded at archive time to the stored payload before checking a receipt. A failed size check returns the existing exact-source path.
9. **Truthful source loss.** If the preserved source is missing or fails archive integrity, report source-unavailable and never claim an exact-source fallback. Reducer failures with an intact original return the recallable handle.

## Verification

Use controlled passing and failing logs with known exact spans. Inject fabricated quote, wrong digest and inconsistent exit-status cases and prove they are rejected. Prove diagnosis can recall the original exact region after reduction and that no contradictory reducer receipt can create green verification evidence.
