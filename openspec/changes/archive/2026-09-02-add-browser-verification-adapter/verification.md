# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent manual semantic OpenSpec review of the accepted `browser-verification` spec delta against the implementation (capability descriptor, bounded adapter, project-owned allowlist, docs, fixture), plus a real end-to-end exploratory run and the automated platform checks below.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

Reviewed each accepted requirement in `specs/browser-verification/spec.md` against the delivered behavior:

- **Web projects can opt into browser verification.** `browser-verification` is authored
  through the #87 lifecycle (`capability_manager.py create`); it is `tool-backed`,
  `auto+explicit`, adapter `scripts/browser_verification.py`, disabled by default in
  `dev-platform/capabilities.toml` and `template/dev-platform/capabilities.toml`. No
  browser-specific registry, selection semantics, materialization or update path was
  added. `tests/test_browser_verification.py::CapabilityMaterializationTests` proves
  opt-out materializes no `.claude`/`.codex` surface and opt-in materializes exactly the
  descriptor marker.
- **Mandatory checks do not depend on the exploratory backend.** The adapter is not a
  member of any `[test_groups]` entry; `run_test_groups.py --all` passes with and without
  `agent-browser` installed. `tests/test_browser_verification.py` never invokes the real
  backend (the `backend-unavailable` path and a stub binary cover the seam).
- **Bounded origins and session state.** `classify_origin` allows only
  localhost/loopback/`*.localhost`/`*.test` by default; `dev-platform/browser-verification.toml`
  widens non-production origins; production origins need list membership *and*
  `--allow-production-origin` and refuse interactive steps. A denied origin raises before
  any navigation. Runtime state (Chrome profile incl. `Cookies`, screenshots) is written
  only under the git-ignored `.dev-platform/browser-verification/<run>/`; `record_run`
  rejects an evidence directory that already holds session-state files and
  `_assert_evidence_sanitized` refuses evidence carrying cookie/credential/profile keys.
- **Evidence integrates without a second completion status.** `browser-evidence.json` is
  referenced from this receipt; no new `OpenSpec-Verify` value or completion state exists.
- **Regression promotion is reviewed-only.** `promote` emits a scaffold with
  `applied: false` and writes no test file
  (`RegressionSeamTests::test_promote_describes_but_never_writes_a_test`).

## Real end-to-end exploratory run

`agent-browser@0.36.0` installed as local dev tooling (Chrome for Testing 152 downloaded to
`~/.agent-browser`, outside the repo). Fixture `tests/fixtures/browser-verification-app/`
served on `http://127.0.0.1:8091`.

| Flow | Command | Outcome |
| --- | --- | --- |
| Good checkout | `plan` + `run` on `flows/checkout.json` | `expected-state-observed`; assertion `"Order confirmed"` present; 5/5 steps ok |
| Controlled regression | `plan` + `run` on `flows/checkout-regression.json` | `regression-detected`; assertion `"Order confirmed"` absent — exploratory detection |
| Deterministic seam | `promote` + `RegressionSeamTests::test_fixture_encodes_one_controlled_regression` | the same observable (`"Order confirmed"` reachable) is reproduced without a browser; `promote` describes a Playwright scaffold, does not apply it |
| Disallowed origin | `plan --base-url https://shop.example.com` | exit 2, no navigation performed |

Captured evidence: `evidence/browser-evidence-good.json`,
`evidence/browser-evidence-regression.json`, `evidence/regression-scaffold.json`. No cookie,
credential or profile bytes appear in any captured evidence; the Chrome profile with its
`Cookies` store stayed under the ignored runtime directory and was removed after the run.

## Automated checks

- `python3 -m compileall -q template/scripts scripts` — pass
- `python3 scripts/check_docs_links.py` — pass
- `python3 scripts/render_agents_md_smoke.py` — pass (3 profiles)
- `python3 scripts/managed_projects.py validate` — pass
- `python3 scripts/capability_manager.py audit` — pass
- `python3 scripts/capability_manager.py evaluate browser-verification --fixture dev-platform/evals/browser-verification-pilot.json --runtime fixture --runs 3` — 20/20 cases pass, 2 quality comparisons improved
- `openspec validate add-browser-verification-adapter --strict` — valid
- `python3 template/scripts/openspec_lifecycle.py check` — OK
- `python3 scripts/run_test_groups.py --verify-coverage` — 793 declared == 793 discovered, no gaps/dupes
- `python3 scripts/run_test_groups.py --all` — see `automated-checks.json`

An initial parallel full-suite run hit a 10s subprocess timeout inside
`tests/test_publication_recovery_cli` (protected-merge race helper), unrelated to this
change. That module passed in isolation (14/14) and the change touches no publication code;
classified as environmental nondeterminism, not a regression.
