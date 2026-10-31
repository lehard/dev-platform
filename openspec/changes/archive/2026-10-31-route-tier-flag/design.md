## Decisions

- **Mapping in the source wrapper.** `dogfood_task.py` owns a fixed `TIER_PROFILES = {"R1": "routine", "R2": "standard", "R3": "complex"}` and passes `--profile <profile>` to the engine. It does not call `start_tier_routing.tier_to_profile`, which refuses R1 for authored execution: an explicit tier keeps exactly today's explicit-profile outcome (approved ADD choice 1).
- **Explicit refusal.** The route parsers keep a `--profile` option only to fail: argparse action that raises a parser error "--profile was replaced by --tier R1|R2|R3". No value is mapped.
- **Engine untouched.** `template/scripts/model_routing.py` keeps `--profile` (downstream callers); only its "pass --profile explicitly" error text adds the source `--tier` spelling (approved ADD choice 2).
- **Docs.** AGENTS.md lines are replaced in place (120-line budget, `test_root_guidance_contract`).
