# Proposal: Add Browser Verification Adapter

## Why

Automated unit and integration checks can pass while a user-visible web flow is still
broken. Dev Platform needs a reusable, opt-in browser verification layer that lets an agent
gather bounded exploratory evidence of a real UI flow, while deterministic Playwright /
project E2E stays the repeatable acceptance authority. Without a shared adapter every web
project would reinvent origin safety, session-state hygiene and evidence handling, and
exploratory automation would drift toward an ungoverned production control plane.

## What Changes

- Consume the shared optional engineering capability lifecycle from Development Backlog #87
  for identity, provenance, opt-in, provider materialization and update/removal; introduce
  no browser-specific registry, config store, materialization or update path.
- Add a provider-neutral **Browser Verification Adapter** (`browser-verification`
  capability) for managed projects with a web UI. It is disabled by default and only
  materializes when a project opts in.
- Exploratory mode drives a real controlled browser flow through a pinned
  `agent-browser` (`vercel-labs/agent-browser`) backend, producing bounded
  DOM / accessibility / navigation / screenshot-pointer evidence. The backend is
  development tooling referenced through the #87 tool-backed capability, never an
  application production dependency.
- Deterministic acceptance stays with Playwright / project E2E. The browser agent never
  runs in a mandatory CI test group and its absence never blocks ordinary project CI.
- Browser verification defaults to localhost / loopback / `*.test` origins. Broader
  non-production origins require an explicit entry in a project-owned
  `dev-platform/browser-verification.toml` allowlist; production origins additionally
  require a per-run governed authorization flag. Disallowed origins or write/submit
  intent fail closed.
- Cookies, credentials, browser profiles, cache and sensitive screenshots stay
  machine-local or sanitized under an ignored runtime directory; they never become
  tracked platform/project source or reusable package evidence.
- A discovered exploratory regression may be promoted into a deterministic regression
  scenario by ordinary reviewed work, never by automatic mutation.
- Browser verification evidence integrates into the existing OpenSpec verification
  lifecycle and `verification.md`; it introduces no second completion status.

## Outcome and success evidence

Binary / directly observable:

- `capability_manager.py list` shows `browser-verification` (`enabled: false` by default);
  `audit` is clean with the capability enabled and disabled.
- On a representative local web fixture the adapter drives a controlled flow and writes a
  bounded `browser-evidence.json` describing the expected end state; no cookie, credential
  or profile bytes appear in that evidence.
- One controlled UI regression in the fixture is detected by exploratory mode and is
  reproduced by a deterministic test asserting the same observable difference (the
  exploratory → deterministic seam); where a live backend is unavailable the run reports
  `backend-unavailable` distinctly from a flow failure and the deterministic seam test is
  the primary evidence.
- A run targeting a non-allowlisted origin, or a production origin without the governed
  flag, exits non-zero and performs no navigation.
- A managed project that does not opt in gets no browser skill surface, no
  `agent-browser` dependency and no mandatory browser step; `run_test_groups.py --all`
  does not depend on the backend being installed.
- No browser-specific capability registry, selection file semantics, materialization or
  update path is added; the only new project-owned file is the origin allowlist.

## Non-goals

- Replacing Playwright or CI as the deterministic acceptance authority.
- Automatic production write-actions.
- Storing user browser sessions, cookies or profiles in git.
- A mandatory browser run for every project or every task.
- A universal remote-browser service in this first version.
