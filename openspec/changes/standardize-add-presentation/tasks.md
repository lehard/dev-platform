## 1. Projection

- [x] 1.1 `template/scripts/add_intents.py`: validate the optional element and choice fields (type errors fail `validate-add`); add `render_add` with the derived state mapping and the fixed Russian section order; add the `render-add` subcommand with required `--requirement`; no file writes.
- [x] 1.2 Reuse `_validate_add_document`, `add_content_digest` and the existing freshness result; a stale approval digest is a state, other structural errors fail explicitly.

## 2. Canonical guidance

- [x] 2.1 `dev-platform/capabilities/add-intents.md` + template mirror: content-boundary section (five destinations, test question, four examples, judgement-not-gate), standard presentation section (run `render-add`, relay, compose with selective-domain-interrogation, no extra stop), updated safety text; refresh `.toml` `content_sha256` through the existing mechanism.
- [x] 2.2 `dev-platform/evals/add-intents-pilot.json` + mirror: cases for detailed BR, real delta, reused contract, open alternative, product uncertainty, no-ADD path with objective verifiers.
- [x] 2.3 Pointers in `docs/engineering/agent-workflow.md`, `engineering-capabilities.md` (+ template copies) and `AGENTS.md` / `template/AGENTS.md.jinja` without restating the rules and within the root-guidance line limit.

## 3. Tests

- [x] 3.1 Renderer behaviour tests on ADD fixtures for every state, every section omission rule, product vs architecture question separation, recommendation/options display, stale approval after content edit, invalid ADD failure, read-only (no file written), determinism.
- [x] 3.2 Guidance content tests (five destinations, test question, examples, labels match renderer), no-new-gate assertions (no new status store, registry, validator, command other than `render-add`), schema version and existing `approve-add`/`decompose` behaviour unchanged.
- [x] 3.3 Existing template-contract tests (delivery of the capability file, descriptor, eval and AGENTS pointer through Copier) pass with the updated files; no project edit is required.

## 4. Readiness

- [x] 4.1 Provider-neutral behavioural check: the renderer tests prove byte-identical output for the same ADD and identical structure per state; no live multi-agent run is performed or claimed.

## 5. Delivery

- [x] 5.1 Required platform checks, truthful verification, archive, retrospectives, publication.
