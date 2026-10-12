## 1. Editorial model
- [x] 1.1 Add the node file loader with per-kind strict keys, transitions, links and source bindings.
- [x] 1.2 Add completeness and finished-text validation and derived back-links.
- [x] 1.3 Keep the eight stage ids and the level-3 map branch; wire stage pages to node files.

## 2. Visual system and pages
- [x] 2.1 Replace templates and CSS with the approved visual system: title zone, legend, framed workspace, tree, node panel with three zones, "Внутри · N", sources on request.
- [x] 2.2 Generate the lifecycle SVG schema from transitions and the narrow-screen vertical variant.
- [x] 2.3 Generate overview, stage, mechanism, topic and coverage pages at the decided addresses; preserve existing URLs.

## 3. Non-blocking drift
- [x] 3.1 Add review stamps, drift warnings in `check`, `mark-reviewed`, the site marker and the selected-checks surface.
- [x] 3.2 Add the PR annotation and the isolated post-merge `drift-issue` job and command.

## 4. Content
- [x] 4.1 Author the approved texts for the overview, stage "Запрос и требования" and mechanism "Независимое ревью и доработка", plus definitions for every node of the semantic map.

## 5. Tests, documentation and delivery
- [x] 5.1 Tests: node validation failures, drift warning not failing, stamp refresh, URL preservation, determinism, no-JavaScript, subpath, workflow contract, downstream boundary.
- [x] 5.2 Update `docs/engineering/explorer.md`; capture desktop and 390 px screenshots of the three screens; run full validation and semantic OpenSpec verification.
