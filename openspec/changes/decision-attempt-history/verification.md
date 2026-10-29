OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the documentation diff against the decision-registry delta, proposal, design and tasks; `openspec validate --strict`; documentation link and Explorer checks; capability fixture eval; private-reference guard; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Owner decision (BR-781, 2026-10-23): variant A of three — link OpenSpec, `docs/decisions/` and friction root issues by three rules, no new registry; a separate `docs/problems/` registry and an ADR artifact in the OpenSpec schema were rejected.
- Depth `deterministic`: the Requirement fixes the rules, their destinations and the DEC-0004 content.

## Completeness

- Rule 1: `docs/engineering/agent-workflow.md` ("Problem and decision history"), `docs/engineering/task-intake.md` (Requirement content authoring) and the `requirement-authoring` capability in both copies (section 5).
- Rule 2: `agent-workflow.md` and the record threshold and contract in `docs/decisions/README.md`.
- Rule 3: `docs/engineering/openspec-workflow.md` ("Author the outcome contract").
- DEC-0004 `docs/decisions/0004-main-advance-revalidation.md`: twelve attempts with PR numbers, the current classifier choice, rejected and deferred options, revisit triggers; indexed in the registry.
- Root issue lehard/dev-platform#553: the list of attempts was appended (comment 6484570511).
- Spec: decision-registry ADDED requirement with three scenarios; no rationale in the spec, no requirement restated in DEC-0004.

## Correctness

- Public text uses `BR-N` identities and public PR numbers only; the private-reference guard passes.
- The capability hash, its template copy and both eval fixtures carry the new content digest; `capability_manager.py update requirement-authoring --change-kind material --runtime fixture` passed 20 of 20 cases and `audit` reports no issues.
- Generated-project template docs are unchanged: generated projects have no decision registry, and the shared capability wording is repository-neutral.

## Coherence

- The three rules use the same wording and the same anchor (`agent-workflow.md#problem-and-decision-history`) from task intake, OpenSpec authoring and the registry README.

## Noticed, not changed

- The `requirement-authoring` descriptor hash and its eval fixtures must be refreshed by hand after a content edit; `capability_manager.py update` only verifies them.
