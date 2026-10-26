## Decisions

- **One rule.** The repeated-run refusal and archive reuse call `openspec_lifecycle.check_evidence_reuse` through `automated_evidence_reuse` (managed) and `quick_evidence_reuse` (quick), the rule finish already uses (BR-785). No second notion of "same content".
- **Refuse, do not silently skip.** A repeated evidence-producing run exits non-zero with the evidence path and reason, so a manual rerun is visibly unnecessary. Archive decides first and does not call `select_checks` when evidence is reusable, so the refusal never stops archive. Finish already skips reusable evidence before calling `select_checks`. Coordinator finalization runs without `--evidence` and is unaffected.
- **Only when evidence exists.** An absent evidence file means nothing to compare; the run proceeds. A decision error (git, selection) stops explicitly.
- **Guard reuse.** `select_checks` calls `private_lineage.require_clean_candidate`, the same guard archive runs first; it is a no-op where private lineage is disabled and stops when enabled and missing.
- **Unavailable precheck stops.** Historical evidence shows no `unavailable` outcome in 147 archived runs, so stopping costs nothing in normal operation and turns a runner fault into a named, early failure instead of a 20–40 minute run. The outcome is recorded as the precheck-phase failure.
- **Scope gate.** `select_checks` already calls `enforce_scope_gate`, which computes the task's own diff against the observed `origin/<main>` and treats declared generated files as soft (BR-777); no change.
