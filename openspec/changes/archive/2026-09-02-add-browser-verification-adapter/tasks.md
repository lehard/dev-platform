- [x] Confirm the #87 optional engineering capability lifecycle is the sole source of
      identity, opt-in, materialization, provenance and update/remove; add no parallel path.
- [x] Re-check current `vercel-labs/agent-browser` capabilities, license and platform
      support; pin the exploratory backend (`agent-browser@0.36.0`, Apache-2.0) by version
      and dist shasum.
- [x] Author the `browser-verification` canonical descriptor and instruction file
      (`tool-backed`, `auto+explicit`, adapter `scripts/browser_verification.py`) via
      `capability_manager.py create`; leave it disabled in the project selection.
- [x] Implement `template/scripts/browser_verification.py` (+ source shim) with
      `plan`, `run`, `promote` subcommands: default-deny origin resolution, governed
      production grant, refusal of write/submit-to-prod intent, bounded evidence envelope,
      ignored runtime-state directory, and an explicit `backend-unavailable` outcome.
- [x] Add the project-owned `dev-platform/browser-verification.toml` origin allowlist
      (localhost/test defaults in code; file only widens) in the source repo and template.
- [x] Ignore `.dev-platform/browser-verification/` in `.gitignore` and the template.
- [x] Extend the `browser-verification` spec delta so every acceptance criterion has a
      scenario: opt-in web verification, non-opt-in projects unaffected, bounded
      origins/session state, evidence integrates without a second completion status, and
      reviewed-only regression promotion.
- [x] Add `scripts/browser_verification.py` to `platform_doctor.REQUIRED_COMMON`.
- [x] Create the representative web fixture (`tests/fixtures/browser-verification-app/`
      with a good flow and one controlled regression flow).
- [x] Add the deterministic pilot eval fixture
      (`dev-platform/evals/browser-verification-pilot.json`, + template) and record the
      capability eval decision.
- [x] Add `tests/test_browser_verification.py` (no browser backend required) and register
      `test_browser_verification` in a `dev-platform/checks.toml` test group (+ template)
      so `run_test_groups.py --verify-coverage` stays exact.
- [x] Add `docs/engineering/browser-verification.md` (+ template), link it from
      `docs/engineering/engineering-capabilities.md`, and add the contract-table row in
      `AGENTS.md` and `template/AGENTS.md.jinja`.
- [x] Run a real local exploratory flow against the fixture (good + regression) and
      capture bounded evidence, or record `backend-unavailable` with the deterministic
      seam test as primary evidence.
- [x] Run `compileall`, `managed_projects.py validate`, `run_test_groups.py --all`
      (+ `--verify-coverage`), `capability_manager.py audit`, `openspec_lifecycle.py check`
      and semantic OpenSpec verification; record `verification.md` and
      `automated-checks.json`; resolve the friction checkpoint; archive and publish.
