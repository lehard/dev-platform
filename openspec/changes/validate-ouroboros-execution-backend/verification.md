# Verification: Ouroboros execution-backend compatibility pilot

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review against the accepted proposal, design, delta specification, exact pilot evidence and current Dev Platform acceptance harness; independent-review automation is disabled for this repository
Automated-Checks-Evidence: automated-checks.json

`PASS` verifies that the bounded pilot was executed and reported according to
its contract. It does not mean that Ouroboros passed: the evidence-backed pilot
decision is `reject-for-now`.

## Automated validation

Executed in the assigned worktree on branch
`agent/validate-ouroboros-execution-backend`:

- `python3 -m compileall -q template/scripts scripts` — PASS (3.350 s).
- `python3 scripts/managed_projects.py validate` — PASS (0.119 s).
- `python3 scripts/run_test_groups.py --all` — PASS (229.482 s).
- `python3 template/scripts/openspec_lifecycle.py check` — PASS.
- `openspec validate validate-ouroboros-execution-backend --strict` — PASS.
- `python3 scripts/check_docs_links.py` — PASS.
- `git diff --check` — PASS.

The first three commands were selected and captured by the repository check
selector in `automated-checks.json`. The remaining lifecycle, strict OpenSpec,
documentation, and whitespace checks were run explicitly because the change is
a durable experimental decision artifact even though it retains no runtime
code.

## Completeness

PASS.

- **Bounded compatibility evidence:** both accepted historical cases were
  reconstructed from their exact pre-change base and canonical archived
  OpenSpec/task package. Each immutable Seed hash and candidate execution
  identity is recorded in `pilot-report.md`.
- **Preserved authority:** Dev Platform retained issue/package identity,
  OpenSpec, workspace assignment, acceptance, publication and lifecycle
  completion. Ouroboros received only a one-way generated execution artifact
  and operated under `/tmp`.
- **Independent acceptance:** neither candidate terminal result was trusted.
  The produced implementation was applied without candidate-written tests to a
  current-main acceptance clone and run against the current relevant harness;
  both cases failed, with exact failed behavior recorded.
- **Native evidence reuse:** the report uses durable #94 and #30 native
  verification durations/results. Missing historical routing and comparable
  token/request/cost data remain explicitly unknown; no duplicate native model
  execution was performed.
- **Maintenance leverage:** the report names the provider/session, worktree,
  retry/recovery, and observability responsibilities that could theoretically
  be substituted, then explains why the observed extra Seed/state/verifier
  lifecycle and failed acceptance justify retiring none of them now.
- **Single decision:** exactly one current outcome, `reject-for-now`, is
  recorded together with candidate identity, replay outcomes, intervention,
  coupling, directional efficiency evidence, missing metrics, containment, and
  an event-based revisit gate.

## Correctness

PASS.

- Ouroboros `main` commit
  `c1b77f7b965eac9c2b622ebc4b66c2f617da2a00` (`0.53.1.dev7`) was used instead
  of known-regressed stable `v0.53.0`; the exact stable tag and tested commit
  are distinguished rather than conflated.
- Replay #94 ended with one failed and one dependency-blocked criterion after
  1045.224 s. Current `managed_task_exact_state` acceptance passed 18/21 and
  failed the three exact-identity mismatch cases described in the report.
- Replay #30 ended with one failed and two dependency-blocked criteria after
  775.532 s. Current `tests.test_model_routing` acceptance ran 59 tests with 11
  errors and 1 failure because core report/CLI contract surfaces were absent.
- Both candidate runs independently reproduced the same fat-harness rejection
  of truthful `files_touched` / `tests_passed` claims after retry. The report
  does not mislabel that terminal behavior as success, and also does not hide
  the separate implementation defects found by Dev Platform acceptance.
- The candidate/native durations are identified as directional, non-normalized
  evidence; unavailable usage/cost metrics are not inferred.

## Coherence and negative boundaries

PASS.

- The design required stopping rather than expanding ownership when reliability
  or broad coupling failed. The result follows that gate and retains no
  repository adapter, configuration, or production route.
- Before report completion, the Dev Platform integration checkout was clean;
  the assigned task worktree contained only this OpenSpec change. Ouroboros
  worktrees and state were confined to the explicit pilot root. No candidate
  process mutated a sibling worktree.
- No Ouroboros execution invoked GitHub/project mutation, publication, release,
  rollout, archive, or task completion. The managed issue remained under the
  Dev Platform lifecycle and native execution remains the default.
- The temporary state-root shim and managed-package preparation bundle were
  removed after evidence extraction. Remaining report content is evidence, not
  executable integration glue or a competing specification.

No material divergence remains between the proposal, design, delta requirements,
task checklist, or pilot report.
