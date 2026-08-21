# Verification: standard-profile lifecycle compatibility

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic review (completeness, correctness, coherence) against the spec deltas plus targeted profile-matrix/doctor/routing tests and the complete platform test matrix.
Automated-Checks-Evidence: automated-checks.json

## Completeness

- `template/scripts/model_routing.py`'s `prepare()` now records a truthful
  `topology` (`standalone-clone` vs `linked-worktree`) for every route,
  covering both new requirements: a standard-profile task with no linked
  worktree can record a parent-only route, and every write-capable
  delegation entrypoint (`dispatch_codex`, `prepare_claude_handoff`,
  `codex_argv`, `claude_agent`) refuses to launch a child from a
  `standalone-clone` route.
- `template/scripts/platform_doctor.py` gained `check_task_start_contract`,
  which imports the rendered `scripts/start_task.py` and probes the exact
  callable surface (`StartedTask`, `start_task`, `cleanup_started_task`,
  `admit_task`, `admission_reason`) that `scripts/start_managed_task.py`
  depends on, instead of only checking file presence; it is skipped for
  `harness_mode != "platform"` and for dev-platform's own `platform_version
  = "source"` self-hosted checkout (which re-executes the template module as
  a CLI shim, not an importable API).
- `tests/upgrade_smoke.py`'s standard-profile lane now also runs
  `scripts/model_routing.py prepare` against the real rendered project and
  asserts `topology == "standalone-clone"`, closing the loop from a
  hermetic unit suite to a genuine downstream-rendered canary.

## Correctness

- `tests/test_model_routing.py::StandaloneStandardCloneRoutingTests` proves,
  against a real single-directory Git checkout (no linked worktree):
  `prepare` records `task_worktree == integration_root ==` the clone with
  `topology="standalone-clone"`; `dispatch_codex`/`prepare_claude_handoff`
  refuse a `routine`/`standard` child with a clear message while `complex`
  is unaffected; `codex_argv`/`claude_agent` refuse the same route read back
  from disk (the raw `codex-argv`/`run-codex`/`claude-agent` CLI paths); and
  a routing record written before this field existed defaults to
  `linked-worktree`, so old records are read back under the strict topology
  they were always recorded under.
- `tests/test_standard_profile_lifecycle_compatibility.py` drives the real
  public `start_managed_task.start_managed_task` composition (mocking only
  the GitHub-touching `discover_task`/`import_task`/`reconcile` adapters)
  against a real standard-profile Git checkout, proving package discovery,
  callable task start, branch semantics and routing-record creation compose
  end to end (dev-platform#62/#298/#300), that a failed managed-start leaves
  no half-created task branch, and that the `light` profile control still
  stays on `main` with no task branch.
- `tests/test_platform_doctor.py::TaskStartContractTests` proves the new
  doctor check passes for a compatible rendered `start_task.py`, fails
  closed for a module missing the contract or one that cannot import, and is
  skipped for `harness_mode="project"` and for the `platform_version=
  "source"` self-hosted checkout.

## Coherence

- The `standalone-clone` exception only ever widens what `prepare()` (route
  *recording*) accepts; every child-writer launch path (`dispatch_codex`,
  `prepare_claude_handoff`, `codex_argv`, `claude_agent`, and
  `record_claude_execution`) still requires `topology == "linked-worktree"`,
  so multi-agent's existing distinct assigned-worktree containment invariant
  is unchanged and covered by the full pre-existing
  `test_model_routing.py`/`test_delegation_containment.py` suites, which
  still pass unmodified.
- `template/docs/engineering/model-routing.md` documents the new
  `standard`-profile parent-only-routing section so downstream operators
  understand why the route succeeds but delegation refuses.
- The downstream local patches referenced by dev-platform#298/#300
  (`lehard/dev-platform#298`, `#300`) are not owned by this repository and
  were not touched here; this change supplies the shared-contract behavior
  those patches worked around, which is the prerequisite the proposal names
  for removing them in their own project, not a claim that removal already
  happened there.

## Self-review (medium-effort code-review pass)

Three real issues were found and fixed before archive, each with a
regression test added:

1. `record_claude_execution` did not refuse a `standalone-clone` route, so a
   caller could bypass `prepare_claude_handoff`'s refusal by preparing a
   route directly and calling `record-claude-execution` on it, marking a
   parent-only route as having an executed delegated child. Fixed by
   routing it through the same `_refuse_child_writer_on_standalone_clone`
   guard; covered by
   `test_record_claude_execution_refuses_a_standalone_clone_route_prepared_directly`.
2. `check_task_start_contract`'s probe cached `start_task.py`'s transitive
   imports (`_platform_common`, `rollout_preflight`, `start_worktree`) in
   `sys.modules` under their bare names, so a second in-process probe
   against a different project root could silently reuse the first root's
   copy instead of genuinely reimporting the second root's own file. Fixed
   by snapshotting and forcing a fresh import of those names per probe, then
   restoring prior state; covered by
   `test_repeated_in_process_probes_do_not_leak_between_project_roots`.
3. The `StartedTask` probe required `dataclasses.fields()` compatibility,
   which would false-fail an equally-compatible plain class or namedtuple
   that managed intake never actually depends on being a `@dataclass`.
   Replaced with a constructor-and-attribute probe matching the real
   keyword contract call sites use.

## Automated evidence

- `python3 scripts/select_checks.py --base origin/main --execute --evidence automated-checks.json --json` — selected the full-trigger check (this change touches `template/scripts/**` and `dev-platform/checks.toml`); all 3 commands passed, evidence in `automated-checks.json`.
- `python3 -m unittest tests.test_model_routing tests.test_platform_doctor tests.test_standard_profile_lifecycle_compatibility -v` — 51 passed.
- `python3 scripts/run_test_groups.py --all` — 703 tests across 13 groups passed (via `select_checks.py` above).
- `python3 scripts/managed_projects.py validate` — OK.
- `python3 template/scripts/openspec_lifecycle.py check` — OK before archive.
