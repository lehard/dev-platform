OpenSpec-Verify: PASS
Automated-Checks-Evidence: automated-checks.json
Verification-Method: equivalent semantic review of proposal, design, delta scenarios, implementation and stubbed regression evidence

This is a local implementation receipt, not terminal delivery. The assigned child context was read before implementation; base
`abce3d9584fd60c34a6431d13092b3a7ff27a565`. No archive, publication, commit or
live GitHub write was performed.

## Coordinator decision and length proof

The canonical design selects **65,536 Python characters**, based on GitHub's
reported HTTP 422 text, “maximum is 65536 characters”, and friction #831. That
failure is coordinator-provided evidence, not an observation made during this
verification. The implementation has one limit constant and measures
`len(serialize_package(package))`, including the complete manifest, artifact
headers, fences, markers and literal artifact contents.

GitHub's [Issue schema](https://docs.github.com/en/graphql/reference/issues#issue)
defines `number` as `Int!`. GitHub's [Int scalar contract](https://docs.github.com/en/graphql/reference/other#int)
gives the range `-(2^31)` through `2^31 - 1`. Issue references here require a
positive number, so the maximum is `2147483647`, giving **B = 10 digits**.
This is the per-repository Issue number, not its global database ID.

GitHub's REST [response-body contract](https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api#about-the-response-body)
explicitly guarantees UTC timestamps in `YYYY-MM-DDTHH:MM:SSZ` form. Therefore
`source_issue_evidence.updated_at` has exactly **20 ASCII characters** and
serializes to 22 characters including JSON quotes. This proof uses the
published format guarantee, not an example or the broader ISO-8601 definition.
`body_sha256` is the actual Python SHA-256 `hexdigest()`: exactly **64 ASCII hex
characters**, or 66 serialized characters including quotes. No JSON escaping
changes either length. Tests exercise different timestamps and source bodies.

The estimate uses length witnesses for these two fields, never publishing
them. All other serialized fields are already known and use the same values
and actual serializer as publication, including the routing receipt, present
or absent process evidence, artifact paths and contents. Derived revision,
parent Requirement and work identity do not appear in the serializer.

For an actual d-digit number, `estimated_length - actual_length = 10 - d`.
Hence a fitting comment can be rejected only when its remaining space is less
than `10 - d`. There is no other reserve. After Issue creation, the code checks
both the number bound and this exact serialized-length equality before
publication; contract drift fails explicitly without substitution or recovery.

## Semantic review

Both added requirements and all five scenarios were checked against the code
and tests. On the fresh-creation path the estimate runs immediately before
`create_issue`; preceding validation and duplicate detection perform no GitHub
writes. An estimate above the limit raises an error naming the change, count,
limit and Issue-number bound. Exact equality follows normal creation,
publication, read-back verification and process linkage. The serializer and
Issue body layout are unchanged. Existing duplicate, resume and supersede
behavior is unchanged; no recovery or splitting was added.

The boundary tests call the real `create_issue` and `publish_package` with a
stubbed transport and inspect every write. They exercise ASCII, Cyrillic and
astral Unicode content; all decimal digit transitions and the maximum Issue
number; comfortably fitting packages; estimated limit and limit plus one;
both ends of the conservative zone; escaped Unicode routing metadata; absent
and maximum-count process evidence; unexpected evidence lengths and numbers;
and propagation of GitHub 422 failures without retries or substitution.
Published packages round-trip through the existing parser. No material
spec/implementation conflict or descriptive-docs/code mismatch was found.

## Successful checks

- `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/prewrite-package-limit/automated-checks.json` — passed, including the full `run_test_groups.py --all` suite and all selected compile, CI Python, Ruff and manifest checks.
- Independent Claude review: spec fidelity had no findings; engineering quality noted the documented contract-drift risk and the separately scoped supersede path, both advisory.

- `PYTHONPATH=tests python3 -m unittest test_managed_task.ManagedPackageLimitTests -v`
  — all 7 new tests pass, including their boundary subcases.
- `PYTHONPATH=tests python3 -m unittest test_managed_task.PublishedManagedTaskVerificationTests test_managed_task.SupersedeTaskTests test_managed_task_exact_state test_managed_execution_intake -q`
  — all 63 related tests pass.
- `python3 -m compileall -q template/scripts scripts` — passes.
- `python3 scripts/check_ci_python.py --workflow .github/workflows/ci.yml --job validate --compile template/scripts --compile scripts --compile tests`
  — passes; local Python 3.13 and CI Python 3.11 compile checks, not CI-runtime tests.
- `python3 -m ruff check scripts template/scripts tests` — passes.
- `python3 scripts/generate_platform_manifest.py --write`, then `--check`
  — only the managed-task script digest changed; 145-file manifest matches.
- `python3 scripts/managed_projects.py validate` — passes.
- `python3 scripts/run_test_groups.py --verify-coverage` — passes; test-group
  membership covers all 3,833 discovered tests without omissions or duplicates.
- `openspec validate prewrite-package-limit --strict` — passes structural validation.
- `python3 template/scripts/openspec_lifecycle.py check` — passes in this
  source-candidate context with the managed change remaining active.
- `git diff --check` — passes.

## Broader-test failures and unchanged-base evidence

The broader managed-task run hit pre-existing shared-workspace permission
failures in these six `ManagedPackageTests` methods (one has two failing
subcases):

```text
test_lagging_project_reports_the_update_command_and_still_creates_the_task_branch
test_reconciled_rollout_prints_detail_and_still_creates_the_task_branch
test_session_deferral_leaves_pending_green_rollout_unmerged_and_start_completes
test_standard_task_start_creates_feature_branch_before_import
test_blocked_rollout_stops_task_start_before_any_branch_exists
test_undeterminable_release_lag_stops_task_start_before_any_branch_exists
```

The error is `shared-workspace preflight failed for group staff`, reporting
missing group rwx/setgid on temporary repositories and their Git directories.
Classification: **pre-existing**, proven by extracting both
`template/scripts/managed_task.py` and `tests/test_managed_task.py` from unchanged
HEAD with `git show`, loading those files in an isolated temporary directory,
and running these six methods. Only the test harness's ROOT/SOURCE paths were
redirected to load the extracted implementation and existing unchanged
dependencies. The baseline reproduced exactly 2 assertion failures and 5
error/subcase reports across the six methods. No other worktree, shared
permission settings or unrelated implementation was modified.

The initial broad command also named a nonexistent
`test_managed_task_provenance` module: that extra import error was an invocation
mistake, not a code regression. Corrected selections ran afterward, including
the successful 63-test run above. A keyword-filtered 36-test run likewise
reported three of the baseline permission errors. The later selected full suite passed outside the child sandbox, as recorded above.

## Limitations and retained issues

- No live GitHub boundary test is authorized or was run. Stubs establish local
  serializer Python-character counts and write ordering; they do not establish
  the live service's current acceptance of Unicode or boundary-size comments.
- GitHub may change its comment limit or number/timestamp contract. A changed
  limit can still produce an explicit GitHub error after creation. If the
  number/timestamp contract is violated, the post-create length guard stops
  publication, but the Issue already exists. No arbitrary safety margin or
  recovery was added to hide this risk.
- Archive and publication remain coordinator lifecycle steps. The semantic PASS
  above records equivalent semantic review; independent Claude review and selected
  checks are recorded separately.
- The task path was reviewed for friction. The baseline permission failure is
  retained as a verification-environment limitation. The platform friction
  checkpoint was later written by the supervisor after review of the task path.
- Existing permissive parsing in `managed_task.run_json` (trying a JSON suffix
  after a parse failure) was observed outside the edited blocks. It was not
  extended or used as recovery for this size check. The pre-existing optional
  priority expression in `create_task` also uses `requested_priority or
  config.default_priority`; it remains outside this bounded change. These
  existing paths are reported rather than broadened or silently rewritten.
