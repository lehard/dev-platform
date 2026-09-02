# Design: Exploratory browser evidence plus deterministic acceptance

## Decisions

1. **Capability mechanics come from #87.** Browser verification owns domain behavior and
   tool safety only. The common capability registry, project opt-in
   (`dev-platform/capabilities.toml`), provider materialization, provenance and
   update/remove all come from the shared optional engineering capability lifecycle. This
   change adds one canonical descriptor (`dev-platform/capabilities/browser-verification.toml`
   plus its instruction file) and no parallel lifecycle.

2. **Tool-backed, not instruction-only.** The acceptance criteria require *enforced*
   fail-closed origin/action boundaries and evidence sanitization, which an instruction
   cannot guarantee. `browser-verification` is a `tool-backed` capability whose adapter
   (`scripts/browser_verification.py`, logic in `template/scripts/browser_verification.py`)
   performs the enforcement. Consistent with the existing `capability-catalog` tool-backed
   capability, the adapter is repository-local development tooling.

3. **v1 drives a real browser.** Exploratory mode invokes a pinned `agent-browser`
   (`vercel-labs/agent-browser`, npm `agent-browser@0.36.0`, Apache-2.0,
   dist shasum `e672393279a620fb6c79f6c00797908631450a04`) through its CLI. The backend is
   referenced through the #87 tool-backed capability contract, not vendored and not added
   to any application production dependency set. If the backend is not installed the
   adapter returns `backend-unavailable` (an explicit outcome, distinct from a flow
   failure) so callers can degrade instead of misreporting a broken UI.

4. **Two modes, different authority.** Exploratory browser runs find and explain UI
   failures. Deterministic Playwright / project E2E remains the repeatable acceptance
   surface. The adapter never registers itself in a mandatory platform or project CI test
   group, and `run_test_groups.py` never requires `agent-browser`.

5. **Opt-in applicability.** The capability is absent from the default
   `dev-platform/capabilities.toml` selection in both the source repo and the template.
   Projects without a web UI enable nothing and receive no browser runtime dependency or
   ritual.

6. **Safe default origins with governed widening.** The adapter always allows
   `localhost`, `127.0.0.1`, `::1`, `*.localhost` and `*.test`. A project widens the set
   through a project-owned `dev-platform/browser-verification.toml`
   (`allowlisted_origins` for extra non-production origins). Production origins must be
   listed in `production_origins` *and* granted per run with `--allow-production-origin`;
   they are never an ordinary allowlist entry. Any write/submit-to-production intent is
   refused unconditionally. A missing allowlist file means localhost/test only.

7. **No durable session leakage.** All browser runtime state — profile, cookies, cache,
   screenshots — is written only under the git-ignored
   `.dev-platform/browser-verification/` directory. The `run` subcommand refuses to emit
   `browser-evidence.json` if it would contain cookie, credential or profile bytes, and
   the bounded evidence envelope stores a screenshot *pointer*, not embedded image bytes.

8. **Evidence integrates, status does not fork.** `browser-evidence.json` is an input to
   the existing semantic OpenSpec verification and `verification.md`. No
   browser-specific `OpenSpec-Verify` value, completion state or second receipt is
   introduced.

9. **Exploration can become regression coverage.** The `promote` subcommand emits a
   deterministic regression scaffold *description* for a discovered defect. It never
   mutates test files; turning it into a real Playwright/equivalent scenario is ordinary
   reviewed work.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Secrets / cookies leak into tracked evidence | Runtime state confined to ignored `.dev-platform/browser-verification/`; `run` refuses evidence containing cookie/credential/profile bytes; evidence keeps a screenshot pointer only. |
| Exploratory automation escapes to production | Default-deny origin model; production requires list membership plus a per-run flag; write/submit-to-prod intent always refused; disallowed target performs no navigation. |
| Scope creep into a production control plane | Adapter is a #87 tool-backed dev capability, never a mandatory CI step; deterministic E2E stays the acceptance authority; non-goals recorded in `proposal.md`. |
| Backend supply-chain drift | `agent-browser` pinned by exact version and dist shasum in the descriptor instruction and docs; the effective capability does not change until a reviewed capability update. |
| Non-web projects pay a browser tax | Capability disabled by default in source and template selection; `run_test_groups.py --all` never imports or requires the backend. |
