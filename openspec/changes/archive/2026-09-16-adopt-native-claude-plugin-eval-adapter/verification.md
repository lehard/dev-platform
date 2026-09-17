# Verification: Adopt native Claude plugin eval adapter

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review against the accepted proposal, design, delta specification, and tasks, backed by a real bounded probe of `claude plugin eval` (Claude Code 2.1.273) plus the full platform test suite; `/opsx:verify` is not available in this environment and independent-review automation is disabled for this repository (`[independent_review] enabled = false`)
Automated-Checks-Evidence: automated-checks.json

## Automated validation

Executed in the assigned worktree on branch `agent/adopt-native-claude-plugin-eval-adapter`:

- `python3 -m compileall -q template/scripts scripts` — PASS.
- `python3 scripts/managed_projects.py validate` — PASS (`3 managed, 7 candidate, 3 excluded`).
- `python3 scripts/run_test_groups.py --all` — PASS after fixing a template/root doc-mirror mismatch (see below); 166 tests across 13 groups, ~24 min wall clock.
- `python3 template/scripts/openspec_lifecycle.py check` — reports this change as the only completed-but-active item, as expected before archive.
- `openspec validate adopt-native-claude-plugin-eval-adapter --strict` — PASS.
- `python3 scripts/check_docs_links.py` — PASS (`no problems found`).
- `git diff --check` — PASS (no whitespace conflicts).

`python3 scripts/dogfood_task.py route-claude` required the change to still be
materialized (active, not yet archived); it was run before archiving, which
meant reverting and redoing an initial too-early archive attempt (see the
non-linear `Archive ...` / `Revert "Archive ..."` commits in this branch's
history). Origin/main also advanced during this task
(`953a19d`/`test: isolate thin CI coverage (#426)`); `dogfood_task.py
reconcile` merged it in (normal merge, no rebase/force-push), and the full
869-test `run_test_groups.py --all` was re-run to green
(`group_seconds_total: 828.959`, `outcome: success`, zero failed groups)
against the reconciled head before this second, final archive.

The first `run_test_groups.py --all` run failed two `test_template_contract` cases
(`test_architecture_health_capability_is_mirrored_in_the_template`,
`test_web_engineering_capability_pack_is_mirrored_in_the_template`): I had edited
`docs/engineering/engineering-capabilities.md` but not its required mirror
`template/docs/engineering/engineering-capabilities.md`. Both files were made
byte-identical and the full suite was rerun; those two failures did not recur.

The rerun's only failure,
`test_publication_recovery_cli.BoundedTestDeadlineHelperTests.test_expired_helper_fails_with_process_identity_and_retained_output`,
is classified **pre-existing / environmental**, not introduced by this change:
it asserts a specific message shape from a helper bound to a hard 0.3s
wall-clock deadline, in a test file this change does not touch. Run in
isolation three times immediately after, it passed deterministically each
time (`0.309s`-`0.310s`). The same code area was the subject of a prior
archived stabilization effort (`stabilize-concurrent-lifecycle-tests`,
commit `cfb5ac1`), corroborating that this specific deadline-bound test is
sensitive to system load under the full parallel suite rather than to this
change's diff (`template/scripts/capability_evals.py`,
`template/scripts/capability_manager.py`, `tests/test_capability_manager.py`,
`docs/engineering/engineering-capabilities.md`,
`template/docs/engineering/engineering-capabilities.md`).

### Real native-CLI preflight (not a unit test; recorded for evidentiary completeness)

Performed outside the repository, in the session scratchpad, against the real
published `@anthropic-ai/claude-code@2.1.273` (npm registry) via `npx`:

- `claude plugin --help` / `claude plugin eval --help` — confirmed the `eval`
  subcommand and its exact flag contract exist (not present in this machine's
  locally installed 2.1.119).
- A bounded real run (`claude plugin eval --runs 1 --max-cost-usd 0.20
  --threshold 0 --trust-plugin --json <path>` against a one-case suite)
  produced a real `--json` report and exited 2 with
  `{"partial": true, "partialReason": "auth_failed", ...}` — the spawned
  child process could not reuse this host-bridged session's authentication.
  This is exactly the credential/runtime boundary `probe_claude_native` and
  the `partial`/`partialReason` handling in `run_claude_native`
  (`template/scripts/capability_evals.py`) are built to classify as
  `blocked/unavailable`, never as a fabricated `not-triggered`.

This real run could not exercise the successful-authentication path (this
environment has no standalone, non-host-bridged Claude Code login available),
so the "native run maps a successful case to `triggered`/`not-triggered`"
path is verified by the deterministic unit tests below against a scripted
fake `claude` executable, not by a second live run. That is the documented
boundary of what this environment could confirm end-to-end.

### New/changed unit coverage

`tests/test_capability_manager.py` (existing group `test_capability_manager`,
already declared in `dev-platform/checks.toml`, so no group-membership change
was needed):

- `test_claude_native_adapter_requires_target`
- `test_claude_native_adapter_is_blocked_unavailable_without_binary`
- `test_claude_native_adapter_is_blocked_unavailable_below_minimum_version`
- `test_claude_native_adapter_maps_native_json_into_provider_neutral_report`
- `test_claude_native_adapter_reports_blocked_unavailable_on_auth_failure`
- `test_claude_native_adapter_rejects_drifted_eval_suite_prompt`

All existing `fixture`/`codex` runtime tests
(`test_direct_deterministic_eval_has_positive_negative_and_quality_evidence`,
`test_unsupported_provider_is_not_counted_as_negative_trigger`,
`test_timeout_remains_incomplete_not_a_negative_trigger`, and the rest of the
29-test module) pass unmodified, confirming the `fixture`/`codex` code paths
were only refactored (shared `_compose_report`/`_summarize`), not changed in
behavior.

## Completeness

PASS against `tasks.md`, all nine items checked with concrete evidence inline.

- **Version/provenance:** confirmed the exact CLI version boundary
  (`2.1.119` lacks `eval`; `2.1.269`-`2.1.273` have it) against the real npm
  package, not from the backlog issue's claim alone.
- **CLI contract, JSON schema, exit codes, credential requirement:**
  captured directly from `--help` output and one real bounded run (see
  above), not guessed from documentation.
- **Native-to-provider-neutral mapping:** implemented in `run_claude_native`
  and covered by the new tests; fields that cannot be truthfully mapped
  (`quality_comparisons` from native ablation) are explicitly left
  `not-verified`/`None` rather than guessed, and this boundary is recorded in
  `design.md` and the delta spec.
- **Smallest adapter:** no nested `claude -p` runner or event-stream parser
  was added; `run_claude_native` shells out to `claude plugin eval ... --json
  <path>` and reads only that file.
- **Routing:** `capability_manager.py`'s existing `--runtime claude` plumbing
  (`update`, `evaluate`, `eval-decision`) now threads `--target`/
  `--claude-bin`/`--max-cost-usd`/`--timeout-seconds` to the shared core;
  `decision_for` returns `run` for `runtime="claude"` on a material/explicit
  change.
- **Keyless CI path unchanged:** the `fixture`/`codex` branch of `run_fixture`
  was only refactored to share helpers, and its existing tests pass
  unmodified.
- **Blocked/unavailable, not fabricated failure:** covered by three targeted
  tests (missing binary, below-minimum version, auth failure) plus the
  general `_case_result`/`_compose_report` reuse that already keeps
  unsupported/unavailable statuses out of the negative-trigger bucket.
- **No leaked provider-specific structures:** `run_claude_native` never
  copies `promptMarkdown`, `tracePath`, or an HTML report into the canonical
  report; asserted directly in
  `test_claude_native_adapter_maps_native_json_into_provider_neutral_report`.
- **Regression/lifecycle checks:** full `run_test_groups.py --all` passes
  (after the doc-mirror fix), `openspec validate --strict` passes, doc-link
  check passes.

## Correctness

PASS.

- The version gate (`MIN_NATIVE_VERSION = (2, 1, 269)`) matches the real
  boundary found on the npm registry, not an assumption from the backlog
  issue text.
- The `partial`/`partialReason` and per-run `error`-text classification
  (`_classify_run_error`) was validated both against the real CLI's actual
  `auth_failed` output and against unit tests using that same code (real
  string, not an invented one).
- The prompt-hash integrity check (`_case_digest` re-hash against
  `prompt_sha256`) is exercised by
  `test_claude_native_adapter_rejects_drifted_eval_suite_prompt` and raises
  `EvalError` rather than silently trusting drifted content.
- `_compose_report`/`_summarize` factor out logic that was previously
  duplicated inline in `run_fixture`; the existing fixture/codex tests
  passing unmodified confirms the refactor preserved exact prior output
  shape.

## Coherence and negative boundaries

PASS.

- No change to `capability_evals.py`'s data-minimization design: prompt text
  never re-enters the loaded, in-memory fixture; native `promptMarkdown` is
  read only long enough to hash-verify it, then discarded.
- Codex remains explicitly `unsupported`; no symmetry was fabricated.
- `--scaffold`, `--allow-tools`, and `--allow-real-servers` are never passed
  by the adapter, keeping the sandboxing posture the native CLI already
  defaults to.
- The unmapped `quality_comparisons` boundary and the credential/runtime
  boundary are both recorded in `design.md` and the delta spec rather than
  silently absorbed or hidden behind an optimistic guess.
- `docs/engineering/engineering-capabilities.md` and its required
  `template/` mirror were both updated identically, keeping the documented
  contract in sync with the shipped behavior (`No silent divergence`).

No material divergence remains between the proposal, design, delta
requirements, task checklist, and the shipped implementation.
