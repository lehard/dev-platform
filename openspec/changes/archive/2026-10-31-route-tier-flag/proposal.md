## Why

The owner approved one name for routing tiers (DEC-0008, choice 6): tasks and documents say R1/R2/R3, but the source route commands take `--profile routine|standard|complex`, so the lifecycle map has to explain two names.

## What Changes

- `scripts/dogfood_task.py route-claude` and `route-codex`: `--tier R1|R2|R3` replaces `--profile`; the tier maps to the engine profile (R1->routine, R2->standard, R3->complex) and is passed to `model_routing.py dispatch-*` as today. An explicit `--tier R1` behaves like the former explicit `--profile routine`.
- `--profile` on these commands fails with an explicit error naming `--tier`; there is no alias.
- `AGENTS.md`, `docs/engineering/model-routing.md`, `docs/engineering/lifecycle-map.md` and the explorer routing nodes name only tiers; the engine's "pass --profile explicitly" hint also names `dogfood_task.py --tier`.

## Impact

- `scripts/dogfood_task.py`, one hint in `template/scripts/model_routing.py`, tests, docs, explorer nodes, platform manifest.
- Spec: model-routing (requirement added).
- The engine CLI, routing records and configured model bindings are unchanged.
