# Browser verification

Use this capability to gather **bounded exploratory evidence** that a real user-visible web
flow works. It complements, and never replaces, deterministic Playwright / project E2E,
which stays the repeatable acceptance authority.

## When it applies

- The project opts in (`dev-platform/capabilities.toml`) and has a web UI.
- You need to confirm a controlled local/test flow end to end after unit/integration
  checks already pass, or to understand a reported UI failure.

Projects without a web UI do not enable this and get no browser runtime or ritual.

## How to run

The adapter is `python3 scripts/browser_verification.py`. It drives a pinned
`agent-browser` (`vercel-labs/agent-browser`, `agent-browser@0.36.0`, Apache-2.0) backend.
Install the backend as local dev tooling only when the capability is enabled:
`npm install -g agent-browser@0.36.0 && agent-browser install`.

1. `plan --flow-file <flow.json> --base-url http://localhost:<port> [--out run-plan.json]`
   validates the target origin against the allowlist and emits a bounded run plan.
2. `run --run-plan run-plan.json --evidence-dir <change-evidence-dir>` drives the flow and
   writes a sanitized `browser-evidence.json`. If the backend is not installed it reports
   `backend-unavailable` (not a flow failure).
3. `promote --evidence browser-evidence.json` describes a deterministic regression scaffold
   for a discovered defect. It never writes test files.

A flow file is `{"name": "...", "steps": [{"action": "navigate", "target": "/"}, ...],
"expected_end_state": "..."}`. Read-only actions: `navigate`, `wait_for`, `snapshot`,
`assert_text`, `assert_no_text`, `screenshot`, `accessibility`. Interactive actions:
`click`, `fill`, `submit`, `press`, `type`.

## Safety boundary

- `localhost`, `127.0.0.1`, `::1`, `*.localhost`, `*.test` are always allowed. Widen the
  set only through `dev-platform/browser-verification.toml` (`allowlisted_origins`).
- A production origin must be listed under `production_origins` **and** granted per run
  with `--allow-production-origin`; interactive steps against it are always refused.
- All browser runtime state (profile, cookies, cache, screenshots) stays under the
  git-ignored `.dev-platform/browser-verification/`. Never commit it, and never put cookie,
  credential or profile bytes into durable evidence.
- Browser evidence is an input to the existing OpenSpec `verification.md` receipt. It does
  not create a second completion status.
- Promoting an exploratory regression into a deterministic test is ordinary reviewed work,
  never an automatic mutation.
