# Ouroboros compatibility pilot report

## Decision

**`reject-for-now`**

Ouroboros did not complete either historical replay, and neither produced tree
passed the current Dev Platform acceptance contract. Both executions stopped at
the same verifier boundary after two Codex attempts, classifying truthful file
and test claims as unsupported. The candidate also required a local state-root
shim for strict isolation and still needs Dev Platform to retain its existing
managed-task, workspace, verification, publication, and release lifecycle.

This decision does not change the production runtime, routing, or any downstream
repository. Native execution remains the default.

## Candidate identity and supported surface

The execution-time upstream check was performed on 2026-09-03:

- repository: `Q00/ouroboros`, MIT license;
- current stable release: `v0.53.0`, tag commit
  `55aa1aa9871da13ab48c3c29b456c4aa73880c9f` (released 2026-09-01);
- exact tested revision: current upstream `main` commit
  `c1b77f7b965eac9c2b622ebc4b66c2f617da2a00`, reporting version
  `0.53.1.dev7`;
- local runtime: Darwin x86_64, Python 3.13.12, `uv` 0.12.2, Codex CLI
  0.146.1 using the already authenticated CLI session;
- supported surfaces inspected: CLI workflow start/status/cancel/cleanup,
  Python SDK, MCP tools, runtime adapters, and Seed YAML; no dedicated Dev
  Platform or Codex plugin surface was found. The bounded pilot used only the
  CLI plus the built-in Codex runtime.

Stable `v0.53.0` was not selected because upstream's own post-release evidence
reported severe Codex fleet/concurrency regressions. The tested `main` includes
the subsequently merged runtime-drift fixes, so this is a conservative test of
the newest relevant upstream code rather than a known-broken stable build.

## Dev Platform boundary reused

The pilot reused the external-runtime boundary established by backlog #69 and
the runtime-neutral evidence semantics established by backlog #68:

- Dev Platform retained the managed issue/package identity, canonical OpenSpec
  contract, task workspace assignment, acceptance, publication, and completion;
- Ouroboros received an immutable, one-way generated Seed and operated only in
  its own task worktree;
- terminal status, intervention, containment, duration, and unavailable usage
  metrics were mapped as evidence rather than treated as canonical task state;
- candidate success was never accepted without the current Dev Platform test
  contract.

No second Dev Platform adapter framework, task state machine, evidence schema,
or production routing branch was added.

## Historical inputs and translation

### Backlog #94: rollback empty managed-start transactions

- historical pre-change base / PR base:
  `131df2445c2a1dac67363282c2bfe9ba0e7d8931`;
- managed package `prepared_against`:
  `645a81f29a375b50379cd889f1741cb967fdb47a`;
- accepted implementation commit:
  `bcf5a29c2a4ac4c5fc7b716f945d54bebe52f1b2`;
- native evidence: R2 / Claude Sonnet execution, clean containment and no
  escalation; 21 targeted cases and the full suite passed, with the recorded
  native full-suite duration of 233.745 s.

### Backlog #30: routing calibration from execution outcomes

- historical pre-change base / PR base:
  `5675efad50d483ba95110f68e3af04a59c4b7fd6`;
- accepted implementation commit:
  `9de3c4abe23d58af9be6f81b7df3b1930a604146`;
- native evidence: the full suite passed in 224.797 s and the 12 routing
  calibration regressions passed. The historical routing record is absent due
  to the documented routing-gate defect, so exact native request/token and
  intervention metadata remain unknown rather than inferred.

For each case, the Seed was derived mechanically from the archived OpenSpec
proposal/design/tasks: implementation tasks were grouped into ordered acceptance
criteria, while the Dev Platform-only archive/publication task was excluded.
The pilot overlay prohibited archive, push, PR, issue, project, release, and
rollout mutation. The generated Seeds were execution artifacts, not editable
requirements:

- #94 Seed SHA-256:
  `983aa63631dc128fb3b2479bf3263a6e5dd1f4b9028a5e321110d2688aea8177`;
- #30 Seed SHA-256:
  `a35dde2affb4a4eacf0771ab907bd70b3f3bc836d39a04e775c7dca2dcfbe087`.

Both Seeds passed Ouroboros dry-run schema validation before execution.

## Isolation and pilot glue

The candidate was installed with `uv sync --frozen --no-dev` in
`/tmp/codex-ouroboros-102`. Each replay used an independent clone at its exact
historical base under `/tmp/codex-ouroboros-pilot-102`, and Ouroboros created a
child task worktree for the execution.

Ouroboros exposes no state/config-root override separate from the user's home.
To prevent writes to the real `~/.ouroboros` while preserving access to the
existing Codex authentication, the run used a temporary Python startup
shim that redirected only Python `Path.home()` / `expanduser("~")` resolution to
pilot-local state. Its SHA-256 was
`c99bec4fd25508b45b0462fe6e2da2e3e5ce4fe73aa3e4e174df78f9a37c8eb3`.
Telemetry and dashboard startup were disabled. No repository code, persistent
adapter, or production configuration was changed to enable the pilot.

## Replay results

### #94 result

- session `orch_f5aa50f7305d`, execution `exec_457420edc3f5`;
- candidate duration: 1045.224 s; 96 recorded messages;
- terminal outcome: `failed` (1 failed criterion, 1 dependency-blocked);
- the Codex runtime made two attempts, produced changes in
  `template/scripts/start_managed_task.py` and
  `tests/managed_start_transaction_cases.py` (159 insertions, 7 deletions), and
  reported both targeted and full-suite checks passing;
- both attempts were rejected by the Ouroboros fat-harness verifier for
  unsupported `files_touched` / `tests_passed` evidence claims, ending as
  `FABRICATION_SUSPECTED`;
- independent acceptance applied only the produced implementation to current
  `main`, restored current tests, and ran
  `python3 scripts/run_test_groups.py --group managed_task_exact_state`:
  18/21 passed and 3 failed. The candidate implementation recovered through a
  generic path instead of preserving the required exact mismatch fail-closed
  outcomes for existing board-entry, branch, and worktree identities.

Result: candidate terminal **FAIL**; independent Dev Platform acceptance
**FAIL**.

### #30 result

- session `orch_dfae992e83ab`, execution `exec_5bd7045553df`;
- candidate duration: 775.532 s; 59 recorded messages;
- terminal outcome: `failed` (1 failed criterion, 2 dependency-blocked);
- the Codex runtime made two attempts and produced changes in
  `template/scripts/model_routing.py` and `tests/test_model_routing.py`
  (140 insertions, 2 deletions);
- both attempts were rejected by the same fat-harness evidence boundary, ending
  as `FABRICATION_SUSPECTED`; later criteria were never executed;
- independent acceptance retained only the produced implementation over current
  `main` and ran `python3 -m unittest tests.test_model_routing`: 59 tests ran
  with 11 errors and 1 failure. The result implemented only a sample helper and
  omitted the required `routing_calibration` report, minimum-observation
  constant, CLI surface, breakdowns, and advisory decision.

Result: candidate terminal **FAIL**; independent Dev Platform acceptance
**FAIL**.

## Intervention, efficiency, and containment

Neither execution needed a manual resume or restart after launch. Operator work
was nevertheless required to prepare the isolated state shim, derive and hash
the Seeds, extract the candidate diffs, restore current tests, and run the
authoritative acceptance harness. One initial #30 clone was discarded and
recreated because a shared clone from a partial source lacked required objects;
this was pilot setup error and is not attributed to Ouroboros.

The candidate wall-clock durations (1045.224 s and 775.532 s) are both materially
longer than the recorded native full-suite durations (233.745 s and 224.797 s),
and each candidate run invoked multiple expensive test passes before failing.
Those numbers are directional only: they cover different execution scopes and
are not normalized benchmark measurements. Comparable token/request/cost data
was not available from both historical native evidence and candidate status, so
it remains **unknown**.

Containment passed: inspection after both runs found no candidate writes in the
current integration checkout, current managed-task worktree, or sibling
worktrees; the candidate worktrees remained under the pilot-local state root.
Ouroboros performed no GitHub, project, publication, release, or rollout
mutation. The Development Backlog issue remained controlled by Dev Platform.

## Maintenance leverage assessment

In principle, Ouroboros could replace provider-specific session/retry handling,
worktree setup, event collection, status/cancel/cleanup surfaces, and some
execution observability. This pilot does not justify retiring any of that code:

- both representative brownfield changes failed candidate verification and
  current Dev Platform acceptance;
- the candidate adds its own Seed, event store, worktree lifecycle, verifier,
  and recovery semantics while Dev Platform must still retain its canonical
  lifecycle and independent acceptance;
- strict state isolation currently needs a custom shim because no supported
  non-home state-root boundary was found;
- the verifier failure obscured rather than reduced recovery work, and one
  replay also produced materially incomplete implementation.

There is therefore no concrete maintenance substitution available now. Keeping
an adapter would create maintenance before proving replacement value, so all
disposable pilot glue is removed and no integration seam is retained.

## Revisit condition

Reconsider only after all of the following are true:

1. an upstream stable release includes a regression fix for truthful Codex
   `files_touched` / `tests_passed` claims being rejected by the fat-harness;
2. upstream has a reproducible multi-file brownfield Codex regression covering
   that evidence path;
3. Ouroboros provides a supported isolated state/config-root mechanism that does
   not require changing or shadowing the user's home;
4. the exact two historical bases and Seed hashes above can be replayed without
   manual resume/restart, reach candidate completion, and pass the current Dev
   Platform acceptance contract.

Until then, further integration work or a production runtime switch is rejected.
