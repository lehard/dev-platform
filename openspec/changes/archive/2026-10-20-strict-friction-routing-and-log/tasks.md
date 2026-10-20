## 1. Routing and configuration

- [x] 1.1 Require `[promotion].repo` for platform-scope destinations in `destination_for` and `platform_repository`, with a named error and no origin substitution
- [x] 1.2 Propagate configuration read errors and reject invalid values in `process_label`

## 2. Local friction log

- [x] 2.1 Make `read_events` strict with `path:line` errors and add the explicit `tolerate_local_gap` context used only by review-path and accepted `friction-log` gaps
- [x] 2.2 Align `_local_source_status` with the strict parser
- [x] 2.3 Derive content-based ids for id-less events and translate persisted positional `legacy-N` references in routes and attributions

## 3. Verification and delivery

- [x] 3.1 Add regression tests for missing promotion repo, label read errors, malformed/unreadable log, accepted gap and stable legacy ids
- [x] 3.2 Run the selected checks and full validation, record semantic verification, archive and publish
