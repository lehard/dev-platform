## 1. Reconcile current context/efficiency owners

- [x] 1.1 Reconcile current execution-efficiency provenance and #103 context-delegation implementation against this package baseline.
- [x] 1.2 Identify the smallest runtime-neutral owner for observation identity/store/recall and keep provider mechanics inside adapters.
- [x] 1.3 Define eligibility and lifecycle states without a paper-specific universal threshold.

## 2. Implement large-observation lifecycle

- [x] 2.1 Preserve eligible original observations exactly in bounded run/session-local storage before cooling.
- [x] 2.2 Emit a compact reference with stable handle, source/type metadata, original size and bounded excerpt.
- [x] 2.3 Add exact targeted recall by handle and bounded range/query.
- [x] 2.4 Keep small observations and unsupported runtimes on the existing safe path.
- [x] 2.5 Ensure archive/recall failures never silently discard original evidence.

## 3. Evidence and dogfood

- [x] 3.1 Reuse existing efficiency provenance for source/hot/recall bytes/lines, trigger rate/intensity and runtime usage where authoritative.
- [x] 3.2 Keep token/cache fields unknown when the runtime does not expose supported exact measurements.
- [x] 3.3 Dogfood on representative large read/search/command outputs without enabling hard context budgets.

## 4. Regression coverage and delivery

- [x] 4.1 Cover small observation, cold large observation, exact recall, full-recall escape hatch, stale/unknown handle and storage failure.
- [x] 4.2 Verify existing context delegation, routing, managed lifecycle and verification semantics remain unchanged.
- [x] 4.3 Run platform-required checks, archive normally and publish through the standard lifecycle.
