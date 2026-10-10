## 1. Map model and source rendering
- [x] 1.1 Define the `explorer/map.toml` schema and loader with strict validation (unknown keys, duplicate ids, cycles, dangling parent/related, empty sources) and failing diagnostics.
- [x] 1.2 Implement tracked-source resolution with heading-section extraction and the built-in Markdown renderer with fail-closed handling of unsupported constructs; implement collection enumeration for specs, capability descriptors and decisions.
- [x] 1.3 Author the initial `explorer/map.toml` covering platform areas and components from README, `docs/`, ownership, release policy and engineering documents.

## 2. Static site, safety and boundary
- [x] 2.1 Generate index and per-element pages with relative links, persistent navigation tree, parent chain, related elements, source links at the built commit, and VERSION/commit footer; add minimal CSS and optional enhancement script.
- [x] 2.2 Add the public-safety output scan reusing `scripts/public_distribution.py`, deterministic ordering, and explicit failures outside git; add `check` and `build` subcommands and the `.gitignore` entry for build output.
- [x] 2.3 Add the downstream-boundary contract test (rendered project has no Explorer artifacts) and confirm Explorer files are classified platform-only by existing script-parity tests.

## 3. Tests, documentation and delivery
- [x] 3.1 Add unit and fixture tests for validation failures, collection discovery, determinism, unsupported constructs, prohibited-state rejection and relative-link behavior under a subpath.
- [x] 3.2 Write `docs/engineering/explorer.md` and the ownership note; run compile, ruff, full test groups and docs link checks; run semantic OpenSpec verification and complete the authorized lifecycle handoff.
