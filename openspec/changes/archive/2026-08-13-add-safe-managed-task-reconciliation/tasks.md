## 1. Observe stale managed tasks early

- [x] 1.1 Extend supported status/preflight to report task-vs-authoritative-main freshness before expensive validation.
- [x] 1.2 Include bounded exact task/PR/provenance evidence in the diagnostic without exposing machine-local secrets.

## 2. Add safe reconcile/resume

- [x] 2.1 Add one explicit lifecycle reconcile entrypoint reusing current fetch/freshness/publication helpers.
- [x] 2.2 Support unpublished task reconciliation without force/reset/history rewrite.
- [x] 2.3 Support open exact-PR reconciliation with history-preserving, fast-forward-pushable ancestry.
- [x] 2.4 Refuse dirty auto-stash, changed remote head, provenance ambiguity and unsafe repository state.
- [x] 2.5 Return concrete merge-conflict paths and a resumable state.

## 3. Integrate with validation/publication

- [x] 3.1 Ensure reconciled heads rerun the current required validation rather than reusing stale evidence.
- [x] 3.2 Resume the existing exact-head publication flow on the same PR after successful reconciliation.
- [x] 3.3 Keep repeated reconcile idempotent.

## 4. Verification

- [x] 4.1 Add regression scenarios for process issues #190 and #219.
- [x] 4.2 Cover unpublished, open-PR, dirty, conflict, changed-head and already-current paths.
- [x] 4.3 Run relevant lifecycle/OpenSpec/template checks and semantic verification, then archive normally.
