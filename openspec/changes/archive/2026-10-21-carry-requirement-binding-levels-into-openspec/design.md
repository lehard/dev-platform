## Context

The three binding levels are defined once, in `requirement-authoring.md` section 4. The deterministic and bounded-evidence pre-authoring paths skip ADD and go straight from the Requirement to OpenSpec authoring, so the rule must live in the OpenSpec authoring guidance, which every path reaches; the ADD pipeline gets a short placement rule only for the material-design path.

## Decisions

1. **Canonical place.** The full rule and the worked example live in the "Author the outcome contract" area of `openspec-workflow.md`, in both the central and the generated copy (the existing test `test_outcome_oriented_openspec_authoring_contract_is_shared` already binds the two copies to one authoring contract). `add-intents.md` and `requirement-authoring.md` reference it instead of restating it.

2. **How each level is written in OpenSpec.** Fixed: exact value in the requirement text and a scenario that checks it. Meaning fixed: the requirement names the property the user must be able to observe ("is visible next to the balances", "states that…"), and the scenario checks the property, not a widget. Delegated: nothing in the requirement; at most a design note that the executor chooses. Constraints (money, data, security, accessibility, compatibility) are never relaxed by delegation.

3. **Examples and mockups.** An example, illustrative value or mockup informs the meaning; it binds exactly only what the Requirement marked as fixed.

4. **Worked example without private references.** The public repository does not name private projects or private backlog issues. The example states the case by its content (cash-flow report, balance strip, warning about places without a known balance) and is complete without the source link.

5. **OpenSpec CLI rule.** One `specs` rule in `openspec/config.yaml` and `template/openspec/config.yaml.jinja` keeps the instruction in the context the OpenSpec CLI gives the authoring agent.

6. **No new mechanism.** No new section in the Requirement format, no stage, gate, validator, classifier or field in ADD/intents/handoff schemas.

## Risks / Trade-offs

- Wording drift between the central and generated copies: covered by the shared-contract test, which gains assertions for the new rule.
- Downstream projects with a locally edited `openspec/config.yaml`: Copier merges one added list entry through the existing managed-file update path; no migration.
