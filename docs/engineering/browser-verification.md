# Browser verification adapter

Browser verification is an opt-in optional engineering capability
(`browser-verification`) that lets an agent gather **bounded exploratory
evidence** that a real user-visible web flow works. It is orthogonal to
`workflow_profile` and is delivered, opted into, materialized, pinned and removed
through the [optional engineering capability lifecycle](engineering-capabilities.md);
it adds no browser-specific registry, selection semantics or update path.

## Two modes, different authority

| Mode | Tool | Authority |
| --- | --- | --- |
| Exploratory | `scripts/browser_verification.py` driving a pinned `agent-browser` backend | Find and explain UI failures; produce bounded evidence of an expected end state |
| Deterministic acceptance | Playwright / the project E2E suite | The repeatable pass/fail authority; unchanged by this capability |

The exploratory adapter never joins a mandatory CI test group, and
`run_test_groups.py` never requires the backend. A green exploratory run is
supporting evidence, not an acceptance decision.

## Enabling it

```bash
python3 scripts/capability_manager.py enable browser-verification
npm install -g agent-browser@0.36.0 && agent-browser install   # local dev tooling only
```

Projects without a web UI leave it disabled and receive no browser skill surface,
no backend dependency and no mandatory browser step.

### Pinned backend

`agent-browser` (`vercel-labs/agent-browser`), npm `agent-browser@0.36.0`,
Apache-2.0, dist shasum `e672393279a620fb6c79f6c00797908631450a04`. The pin lives
in the capability descriptor instruction and in
`template/scripts/browser_verification.py`. The effective capability does not
change because the upstream default branch moves; changing the pin is a reviewed
capability update.

## Running a flow

A flow file describes a short declarative journey:

```json
{
  "name": "checkout",
  "expected_end_state": "The checkout form shows 'Order confirmed' after placing an order.",
  "steps": [
    {"action": "navigate", "target": "/index.html"},
    {"action": "fill", "ref": "#email", "value": "buyer@example.test"},
    {"action": "click", "ref": "#place-order"},
    {"action": "assert_text", "text": "Order confirmed"},
    {"action": "screenshot", "name": "checkout-final"}
  ]
}
```

```bash
python3 scripts/browser_verification.py plan \
  --flow-file tests/fixtures/browser-verification-app/flows/checkout.json \
  --base-url http://localhost:8000 --out run-plan.json
python3 scripts/browser_verification.py run \
  --run-plan run-plan.json --evidence-dir openspec/changes/<change>/
```

`run` writes a sanitized `browser-evidence.json`. Its `outcome` is one of
`expected-state-observed`, `regression-detected`, `flow-error` or
`backend-unavailable` — the last is explicitly distinct from a failing flow so a
missing backend never misreports a broken UI.

## Safety model

- **Default-deny origins.** `localhost`, `127.0.0.1`, `::1`, `*.localhost` and
  `*.test` are always allowed. Wider non-production origins require an explicit
  entry in the project-owned `dev-platform/browser-verification.toml`
  (`allowlisted_origins`).
- **Production is separate.** A production origin must be listed under
  `production_origins` *and* granted per run with `--allow-production-origin`.
  Interactive (`click`, `fill`, `submit`, `press`, `type`) steps against a
  production origin are always refused. A denied origin performs no navigation.
- **No durable session leakage.** Browser profile, cookies, cache and screenshots
  are written only under the git-ignored `.dev-platform/browser-verification/`.
  `run` refuses to emit evidence containing cookie, credential or profile bytes,
  and stores a screenshot *pointer*, not image bytes.

## Evidence in the verification lifecycle

`browser-evidence.json` is an input to the existing semantic OpenSpec
verification and the change's `verification.md` receipt. It introduces **no**
second completion status, receipt or acceptance authority. Reference the evidence
file from the normal receipt.

## Promoting a regression

When exploratory mode detects a broken flow, `promote --evidence
browser-evidence.json` emits a deterministic regression scaffold *description*
(`applied: false`). Turning it into a real Playwright / project E2E scenario is
ordinary reviewed work. If no deterministic seam exists yet, say so explicitly in
the change evidence rather than dropping the finding.

## Backend review provenance

`agent-browser` is referenced as pinned development tooling, not vendored. It
drives Chrome for Testing over the Chrome DevTools Protocol. Its Apache-2.0
license and exact version/shasum are recorded above and in the descriptor;
Dev Platform copies none of its source.
