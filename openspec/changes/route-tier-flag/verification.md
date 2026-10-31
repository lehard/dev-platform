OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the model-routing delta, proposal, design and tasks; targeted unit tests (test_central_dogfood_lifecycle 24, test_model_routing and test_agent_instruction_architecture 204, explorer and root-guidance tests 143, all passing); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Material-design pre-authoring; ADD approved by the chat coordinator under the owner's delegation (2026-10-31): an explicit `--tier R1` keeps the former explicit `--profile routine` outcome; the shipped `model_routing.py` engine keeps `--profile`.
- The ADD evidence was refreshed once after `main` advanced (#826) with unchanged content and re-approved.

## Completeness

- `--tier` on both commands with the R1/R2/R3 -> routine/standard/complex mapping: `test_each_tier_routes_as_its_former_profile_on_both_commands`; existing route tests now pass `tier` (R2, R3, omitted).
- Omitted tier still confirms the authored tier (no `--profile` passed to the engine): `test_route_codex_omits_tier_when_confirming_authored_tier`, `test_route_claude_omits_tier_when_confirming_authored_tier`.
- `--profile` refused naming `--tier`, exit 2, nothing routed: `test_removed_profile_flag_fails_naming_tier_and_routes_nothing`.
- Docs and hints: AGENTS.md (line replaced, still 120 lines, `test_root_guidance_contract` passes), `docs/engineering/model-routing.md`, `docs/engineering/lifecycle-map.md`, explorer `routing` and `executor-routing` nodes, the engine's explicit-profile error (test updated).

## Correctness

- No alias and no default: `--profile` never maps to a tier; an unknown tier is rejected by argparse choices.
- Routing outcomes are unchanged: the wrapper passes the same engine `--profile` value as before for each tier.

## Coherence

- Spec delta, proposal, design, tasks, docs and explorer describe the same flag; the platform manifest is regenerated for the engine hint.

## Not verified / limits

- Engine-internal profile names in routing records, help texts of `model_routing.py` and downstream template docs are unchanged by design.
