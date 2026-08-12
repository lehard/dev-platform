## 1. Preflight and guidance inventory

- [ ] 1.1 Reconcile this package against current `project-factory` specs, central/template agent guidance, documentation ownership rules and all active changes touching generated guidance, especially `adopt-gh-aw-process-automation`.
- [ ] 1.2 Inventory meaningful directives in central `AGENTS.md` and `template/AGENTS.md.jinja`; classify each as required always-on context or just-in-time detailed guidance and identify the canonical destination for every moved directive.
- [ ] 1.3 Establish the final mechanical line/size budget near the agreed 80–120 line target, with a short evidence-based justification that it retains all required always-on invariants.

## 2. Refactor central and generated context

- [ ] 2.1 Rewrite central `AGENTS.md` as the bounded vendor-neutral map: source-of-truth model, task-intent boundaries, key safety/stop invariants, canonical entrypoints, ownership/scope rules and concern-to-doc navigation.
- [ ] 2.2 Apply the same context architecture to `template/AGENTS.md.jinja` across workflow profiles while preserving profile-specific safety requirements that genuinely must remain always-on.
- [ ] 2.3 Move/consolidate detailed workflow prose into the appropriate existing central/template docs; create a new thematic doc only where preflight proves no coherent existing destination.
- [ ] 2.4 Keep platform-owned tool-specific adapters thin and reference-based; do not introduce a Hermes-specific parallel process contract.

## 3. Mechanical guardrails

- [ ] 3.1 Add contract tests for central and rendered root-guidance budget plus required navigation/invariant anchors.
- [ ] 3.2 Add/adjust tests proving `CLAUDE.md` and other platform-owned adapters do not become duplicate repository-wide rule sets.
- [ ] 3.3 Render all supported factory profiles and verify relative documentation links/destinations exist in the generated repository and Copier ownership rules remain valid.

## 4. Semantic regression

- [ ] 4.1 Produce migration verification evidence showing every meaningful pre-change root directive is either retained always-on or mapped to one canonical discoverable detailed destination; resolve any orphaned/duplicated rule before completion.
- [ ] 4.2 Run the regression coverage that is actually relevant to the relocated guidance (template/guidance contract tests, doc ownership, render). Do not require an unrelated full Python suite solely because instruction/documentation/template text changed; if executable surfaces change, run the checks relevant to them, and if a directive's meaning intentionally changes, reconcile OpenSpec and add targeted behavioral evidence.
- [ ] 4.3 Specifically verify the latest active retrospective/friction completion requirements remain discoverable and behaviorally unchanged after reconciliation with `adopt-gh-aw-process-automation`.

## 5. Verification and delivery

- [ ] 5.1 Run the platform/template/Copier/OpenSpec validation relevant to this change's risk class and verify the bounded guidance contract against both central source and rendered downstream output.
- [ ] 5.2 Perform semantic OpenSpec verification with explicit evidence that the change reduced always-on context without weakening safety or lifecycle semantics.
- [ ] 5.3 Archive and publish through the normal protected-main lifecycle only after verification passes; include the template/runtime change in the ordinary immutable platform release and reviewed downstream Copier rollout path where applicable.
