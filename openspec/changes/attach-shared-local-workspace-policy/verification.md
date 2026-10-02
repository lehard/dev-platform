OpenSpec-Verify: BLOCKED
Verification-Method: bounded executor semantic review and executable regressions

Implementation is ready for supervisor review; this receipt does not authorize
archive or claim terminal delivery.

The source-policy, hook-composition and registered-project requirements are
implemented by the standalone template runtime and central adapter. Source
admission is independently invoked before shared-workspace preflight/intake
mutation. External policies remain opt-in, new template renderings stay disabled
without the local Git key, and existing projects can use the external launcher
before a reviewed Copier update. The central Mac permission adapter is unchanged.

Checks actually run:

- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 scripts/managed_projects.py validate`: passed (four managed projects).
- `python3 template/scripts/openspec_lifecycle.py check`: passed.
- `git diff --check`: passed.
- `python3 -m unittest discover -s tests -p test_local_workspace.py`: 19 passed.
  Real source rw repairs, restrictive and atomic writes, exclusions, symlinks,
  hardlinks, group/identity refusal, owned task administration, registry discovery,
  runtime update/idempotence, launcher failure/umask, read-only admission,
  hook stdin/arguments/failure, doctor refresh/composition, relative hooks,
  Git-directory hook invocation and removal are covered.
- `python3 -m unittest discover -s tests -p test_shared_writer_guard.py`: two passed
  after explicitly reviewing the new bounded writer/descriptor/lock sites.
- `python3 scripts/run_test_groups.py --all`: failed; failed groups were `fast-b`,
  `fast-c`, `fast-d`, and `model_routing`. Its initial collection declared 1543
  tests; additions during executor repair mean this is not a final-head full-suite
  PASS. The introduced writer-guard failure was repaired and rerun successfully.
- `python3 -m unittest discover -s tests -p test_shared_workspace.py`: one failure
  and three errors, identically reproduced from an unchanged HEAD archive at
  `93aaf8c954c4369f1234db4a37d1b262f3ae3b12`; these four are pre-existing here.
- Final `python3 scripts/run_test_groups.py --group fast-d`: failed only on the
  same four baseline-confirmed shared-workspace cases; runtime and writer-guard
  regressions passed within this group.
- An unchanged-HEAD full source archive reproduced the other six failing managed
  task/profile cases and all three Copier-render profile subcases (seven selected
  test methods: one failure and eight errors). Thus all remaining top-level
  failures from the full run have matching pre-existing baseline evidence here;
  no unrelated permission or Copier behavior was weakened to pass them.
- `python3 scripts/independent_review.py preflight attach-shared-local-workspace-policy`:
  blocked, provider unknown because private managed-task lineage could not be
  verified. No independent perspective was launched; no review evidence is claimed.
- `python3 scripts/dogfood_task.py status --json`: blocked by unavailable GitHub
  API connectivity. Freshness/reconciliation/publication cannot be proven here.

Capability limits and escalation:

The sandbox's Mac temporary filesystem strips setgid after both pathname chmod
and descriptor fchmod. Source rw mutations are tested for real. Composition tests
isolate directory setgid expectations on that volume, while a separate unpatched
check requires the runtime to diagnose unsupported setgid. No production waiver
was added. Foreign ownership tests simulate a caller uid; they do not prove
execution by a second account. LaunchAgent tests verify generated plist and
launchctl orchestration with mocks; no real agent was loaded. Registered Mac
projects and per-user Library paths are outside the delegated write boundary.

Supervisor must run final full validation on a setgid-capable checkout, resolve
confirmed baseline failures, obtain independent review, perform real
registered-project installation and both-user acceptance (or record exact
capability limits), record child friction and parent retrospective, then archive
and publish through the normal lifecycle. Tasks 2.2 and 2.3 remain unchecked.
