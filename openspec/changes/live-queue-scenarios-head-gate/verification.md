# Verification: live-queue-scenarios-head-gate

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta spec against the implementation, scenario by scenario, plus real runs of the runner on the private sandbox. No opsx tool invocation.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- Queue path scenarios: `managed-task`, `red-ci` and `conflict` use the real worker, queue, claims, labels and CI. Only the reviewer binary and the repair writer are scripted.
- Red CI recovers: `fixture/ci-verdict.txt` fails only on GitHub. The queue offered integration repair, the worker read the failed log and briefed the scripted writer, the repaired head merged.
- Conflict with main: the runner moved main after admission, the queue offered integration repair, the writer resolved it and the repaired head merged with both lines on main.
- Hosted finalize: `managed-task` ran the real archive and `openspec validate` on a hosted runner of the private repository.
- Receipt: `run` writes results per scenario, bound to the declared paths at the tested head. `tests/test_live_scenario_gate.py` proves it against real git history: missing, other content, partial, new red, known failure, and a later commit outside the paths.
- Handoff refusal: `dogfood_task.py finish` calls the gate before publication, so it does not touch hosted finalize.
- Surface: the declared paths exist, and the gate's scenarios equal the runner's, both by test.

## Evidence

- Full run: four scenarios passed, all PRs merged by the sandbox App; duration and Actions use are in `docs/engineering/live-scenarios.md`.
- A run without Actions read in the snapshot escalated with `validate` not reported, so that grant stays.
- Earlier failed runs each named scenario, step and observed state, which is how the fixture and runner gaps were found.

## Not verified

- A real model, the sandboxed writer and hosted review: outside these scenarios by design.
- A material review finding followed by repair and the developer semantic gate. This path ran for real on the platform's own delivery, not in a scenario.
- The gate refusing a real handoff: proven by tests, since this change touches no declared path.
- Known failure list: empty today, proven by tests only.
