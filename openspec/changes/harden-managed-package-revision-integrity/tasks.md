## 1. Exact authoring state

- [x] 1.1 Reproduce the stale-local-checkout vs fresh `prepared_against` class from process issue #208.
- [x] 1.2 Make authoring validation observe the exact target revision recorded in the package, without destructive mutation of integration main.
- [x] 1.3 Add deterministic tests for aligned, stale, unavailable and changed target states.

## 2. Source-Issue revision evidence

- [x] 2.1 Add bounded source-Issue revision metadata to newly authored packages/provenance.
- [x] 2.2 Detect meaningful Issue drift before materialization and require an explicit reconcile/acknowledge decision.
- [x] 2.3 Surface post-materialization drift without silently changing canonical OpenSpec.
- [x] 2.4 Preserve compatibility for legacy packages lacking the new metadata.

## 3. Package supersede/repair

- [x] 3.1 Add one supported idempotent supersede/repair entrypoint for an existing managed Issue.
- [x] 3.2 Validate the replacement package completely before activating it.
- [x] 3.3 Preserve bounded predecessor revision evidence while guaranteeing one active revision.
- [x] 3.4 Fail closed on ambiguous/malformed active revision history.

## 4. Verification

- [x] 4.1 Add regression coverage for process issues #208, #210 and #218.
- [x] 4.2 Run relevant managed-task, OpenSpec lifecycle, template/render and strict validation checks selected by current risk policy.
- [x] 4.3 Perform semantic OpenSpec verification and archive through the normal lifecycle.
