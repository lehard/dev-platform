## 1. Canonical standard

- [x] 1.1 Author `dev-platform/capabilities/requirement-authoring.md` and `.toml` (instruction-only, `auto+explicit`, safety boundary: no storage, gate, status or approval) with the rules and small representative examples; mirror both under `template/dev-platform/capabilities/`; register provenance hash.
- [x] 1.2 Add `dev-platform/evals/requirement-authoring-pilot.json` (trigger/not-trigger prompts and quality comparisons with objective verifiers) and its template mirror; document the eval decision.

## 2. Surface wiring

- [x] 2.1 `docs/engineering/task-intake.md` and `template/docs/engineering/task-intake.md.jinja`: fixation and refinement apply the standard before the body is written; stated boundary (no new stage/gate/status).
- [x] 2.2 `docs/engineering/chatgpt-project-protocol.md` and its template copy: connected-GitHub authors read the same canonical file; same sections, labels and read-back as before.
- [x] 2.3 `docs/engineering/agent-instructions.md` and template copy, `docs/engineering/engineering-capabilities.md` and template copy (capability section), `AGENTS.md` and `template/AGENTS.md.jinja` concern row (keep root guidance within its line limit).

## 3. Tests

- [x] 3.1 Content tests: the standard contains each required rule (whole-context classification, supersession, no chronicle, lossless detail, three levels, references and unavailability, selective questions, proportionality, six-point self-check, whole-contract update, scope restraint, privacy) and each non-requirement (no interview/validator/status/ledger/gate/storage).
- [x] 3.2 Case tests over the eval fixture for the cases in design decision 9, plus Claude/Codex rendered skill identity and ChatGPT-protocol link identity.
- [x] 3.3 Compatibility tests: Requirement section list and children marker via `render_requirement_body`/`parse_requirement_body`, capability validate/audit, existing template-contract and root-guidance size tests keep passing; a real Copier render of an operator-integrated and a portable project contains the capability file and the pointers (portable task-intake has no Requirement flow and carries none) with no `capabilities.toml` edit and no provider skill.

## 4. Readiness

- [x] 4.1 Real application of the standard to a long conversation in a managed project can only be observed after this change is released; before release, a real Copier render proves an operator-managed and a portable project receive the standard file and pointers with no project edit (task 3.3). The post-release observation is recorded in the Requirement retrospective, and no live cross-provider behavioral run is claimed.

## 5. Delivery

- [x] 5.1 Required platform checks, truthful verification, archive, retrospectives, publication.
