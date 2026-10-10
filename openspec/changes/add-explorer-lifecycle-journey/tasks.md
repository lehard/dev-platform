## 1. Stage model
- [x] 1.1 Extend the map schema and loader with `[[stage]]` entries and validation (contiguous order, unique ids, existing elements, resolvable sources).
- [x] 1.2 Author the initial lifecycle stages in `explorer/map.toml` with source references into existing canonical documents.

## 2. Pages and navigation
- [x] 2.1 Generate the lifecycle overview and per-stage pages with previous/next navigation, a Lifecycle branch in the navigation tree, and responsive vertical stacking.
- [x] 2.2 Add "used in lifecycle stages" links to component element pages derived from stage elements.

## 3. Tests, documentation and delivery
- [x] 3.1 Add tests for stage validation failures, ordering, cross-links, determinism, no-JavaScript and subpath-relative behavior.
- [ ] 3.2 Update `docs/engineering/explorer.md`; run compile, ruff, full test groups and docs link checks; run semantic OpenSpec verification and complete the authorized lifecycle handoff.
