# Verification: Isolate test friction routing from live GitHub

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of proposal, design, delta spec and implementation against the source issue's acceptance criteria (no `/opsx:verify` tool integration available in this environment); targeted regression coverage for the two affected test files plus the protected full platform validation suite.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Root cause confirmed: `agent_friction.py`'s `cmd_record` calls `route_event()` unconditionally right after the local JSONL append, and `route_event` decides whether to reach GitHub purely from ambient `shutil.which("gh")` / `gh auth status`. The prior fixture in `tests/test_delegation_containment.py` tried to hide `gh` by scrubbing `PATH`/`HOME`, which is host-dependent (Homebrew installs `gh` under `/usr/local/bin` on Intel Macs, inside the fixture's own restricted `PATH`; `gh`'s macOS credential store is keychain-backed, not `HOME`-scoped).
- A second, previously unrepaired instance of the same class exists in `tests/test_delegated_write_guard.py`'s `GuardedDelegationTests`: four tests exercise the real production entrypoint (`run_guarded_delegation`/`run_observed_delegation`) with a synthetic escape (`escaped.txt`, `hooked-escape.txt`, `escaped-on-failure.txt`) and had *no* GitHub isolation at all before this change.
- Fix: an explicit, narrow opt-out seam (`agent_friction.py record --no-route`, threaded through `delegation_containment.record_containment_friction(..., route=False)` and `delegated_write_guard.run_observed_delegation`/`run_guarded_delegation(..., route_containment_friction=False)`), defaulting to `True`/routing-enabled everywhere so every production call site (the single real caller, `model_routing.py`'s `run_observed_delegation` invocation) is unchanged.
- All five real (non-mocked) synthetic-violation call sites across the two test files now pass the explicit opt-out; verified by grepping `tests/` for `record_containment_friction(`, `run_guarded_delegation(` and `run_observed_delegation(` and inspecting every match (the only other matches, in `tests/test_model_routing.py`, are against a fully mocked stand-in and carry no GitHub risk).
- The two primary violation regressions (`test_delegation_containment.py::test_record_containment_friction_writes_local_event_without_github` and `test_delegated_write_guard.py::test_writer_escaping_into_integration_root_is_a_violation_and_records_friction`) additionally place a stub `gh` first on `PATH` that fails the test if invoked, proving the isolation structurally rather than by hoping the host has no reachable `gh`; both pass with the stub present, so the guarantee holds independent of host `gh` availability/authentication.
- Local friction-log assertions (JSONL content, category, `escaped.txt`) are unchanged in both files, so the tested contract for local recording is preserved, not weakened.
- Production routing coverage is untouched: `tests/test_friction_review.py` still exercises `agent_friction.route_event` end to end against a mocked `gh` (issue creation, occurrence-comment update, candidate/duplicate handling, pending retry) with no route-skip involved, so real runtime friction routing is verified unchanged.
- Non-goals honored: `lehard/dev-platform#137` was not touched (no comment/close), no dedupe/fingerprint redesign, no rate limiter, no global production routing switch, no test-framework rewrite.

## Automated checks

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 scripts/run_test_groups.py --all` (643/643 tests, 13 groups, all success — includes the `delegated_write_guard` group and the friction/delegation coverage in `fast-*`)
- `python3 template/scripts/openspec_lifecycle.py check` (post-verification)
- Full platform selection captured in `automated-checks.json` by the archive lifecycle helper
