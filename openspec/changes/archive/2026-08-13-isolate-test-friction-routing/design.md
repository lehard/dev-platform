# Design: Isolate test friction routing from live GitHub

## Current behavior
`delegation_containment.record_containment_friction` shells out to `agent_friction.py record`, which calls `route_event()` synchronously right after appending the local JSONL log (`template/scripts/agent_friction.py` `cmd_record`). `route_event` decides whether to reach GitHub purely from ambient host state: `shutil.which("gh")` plus `gh auth status`. The existing regression, `test_record_containment_friction_writes_local_event_without_github` (`tests/test_delegation_containment.py`), tries to suppress that by clearing `os.environ` and restricting `PATH` to `/usr/bin:/bin:/usr/local/bin` plus a throwaway `HOME`.

That is host-dependent, not hermetic: `/usr/local/bin` is exactly where Homebrew installs `gh` on Intel Macs, and `gh`'s credential store is OS-keychain-backed on macOS rather than `$HOME`-scoped, so on an authenticated host the test can still resolve a real, authenticated `gh` and `route_event` proceeds to mutate `lehard/dev-platform#137`.

## Approach
Add one explicit, narrow seam that only the test fixture uses, instead of extending ambient env/PATH heuristics:
- Give the routing entrypoint an explicit opt-out (e.g. a `route: bool` parameter on `route_event`/`cmd_record`, or a `--no-route` flag on `agent_friction.py record`) that a caller must pass deliberately to skip GitHub routing, independent of what `gh` happens to resolve to on the host.
- `record_containment_friction` keeps invoking `agent_friction.py record` exactly as today for production call sites (no flag), so real runtime events keep routing through the existing `shutil.which`/`gh auth status` gate unchanged.
- The regression test drives the new hermetic seam explicitly and additionally points `PATH` at a stub `gh` that fails the test if it is ever executed, so the guarantee does not silently regress back to relying on PATH/HOME scrubbing alone.
- Local friction-log assertions (JSONL content, category, evidence) stay exactly as tested today; only the GitHub-routing seam changes.

## Risks and mitigations
- Risk: some other synthetic-violation call site forgets to pass the new seam, reopening the leak. Mitigation: the stub-`gh` assertion fails closed (raises if invoked) rather than failing open, so a call site missing the seam is caught by CI instead of silently posting to `lehard/dev-platform#137`.
- Risk: a broad opt-out could accidentally suppress real production friction events. Mitigation: the seam defaults to today's routing-enabled behavior; only the test fixture passes the opt-out explicitly, and an existing/adjacent production-path regression continues to assert `route_event` is exercised for real runtime events.

## Ownership and rollback
Owned by the same platform test/friction-routing surface as `template/scripts/agent_friction.py` and `template/scripts/delegation_containment.py`. No data migration, schema, or persisted-format change; rollback is a plain revert, since the local JSONL friction-log format and the production routing gate are unchanged.

## Constraints
Dependency-light: reuse the existing `agent_friction.py`/`delegation_containment.py` subprocess/argparse pattern, no new external dependency, no secrets or machine-specific absolute paths introduced by the change.
