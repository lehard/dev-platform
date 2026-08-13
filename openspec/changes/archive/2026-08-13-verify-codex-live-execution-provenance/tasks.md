## 1. Real Codex acceptance

- [x] 1.1 Confirm the local authenticated `codex` account is no longer rate-limited (re-check live; do not assume 2026-08-18 has resolved it). Re-checked live 2026-08-13; account recovered ahead of the estimated date. See `pilot-evidence.md`.
- [x] 1.2 Run a real routine/standard `dogfood_task.py route-codex` -> `dispatch_codex()` -> `run_codex()` delegation from a real managed task worktree. Done 2026-08-13 from this change's own worktree.
- [x] 1.3 Confirm the resulting `.claude/model-routing/<change>.json` `execution.participant` has a real `execution_id.value` (thread id), `model.source: selected`, and a truthful `reasoning_effort.source` (`unknown` unless a stronger surface is genuinely confirmed live). Confirmed: real `codex-thread` id, `model.source: selected`, `reasoning_effort.source: unknown`.
- [x] 1.4 If a stronger runtime-confirmed model/effort surface is discovered, record it here and correct `adopt-gh-aw-process-automation`'s pilot-evidence.md to match; otherwise change nothing there. No stronger surface was discovered; `adopt-gh-aw-process-automation`'s pilot-evidence.md is unchanged.
- [x] 1.5 Record the real run's evidence (route record excerpt, command output) in this change's `pilot-evidence.md`. Done.

## 2. Verify, archive and release

- [x] 2.1 Run platform tests, OpenSpec lifecycle checks and strict OpenSpec validation. All green; see `verification.md`.
- [x] 2.2 Record truthful `OpenSpec-Verify: PASS` in `verification.md` and archive `verify-codex-live-execution-provenance` through the lifecycle helper.
- [x] 2.3 Publish the next normal immutable platform release only if runtime/template code changed (i.e. only if 1.4's fix path was needed); otherwise archive/spec bookkeeping alone does not require a release. No runtime/template code changed; no release required.

## Explicitly avoided in this change

- No redesign of the provenance data model.
- No new model-routing behavior.
- No re-verification of the already-closed Claude leg.
