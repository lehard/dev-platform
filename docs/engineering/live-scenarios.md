# Live lifecycle scenarios

Offline acceptance proves transitions with fake GitHub adapters. These scenarios prove the same paths on real GitHub, in a private sandbox repository running the real queue and workers.

## Shape

The sandbox repository runs in source mode. A rendered project cannot host these scenarios: it has no queue. The runner composes the sandbox tree from an exact platform head and the fixture overlay in `dev-platform/live-sandbox/`, and commits it forward on the sandbox main branch. The sandbox CI and checks are the fast fixture, not the platform suite, so coverage is lifecycle behaviour, not platform test duration.

The sandbox is not in the production managed registry, so rollout never sees it.

## Isolation

- Its own GitHub App, installed only on the sandbox. Candidate code runs on its main branch, so the production App key never goes there.
- Its own operator configuration and one-entry registry, written by the runner into its working directory.
- Its own Backlog binding: Issues live in the sandbox and the runner creates and reconciles the sandbox Project and labels. Nothing is written to the production Backlog.
- The runner refuses before any write unless the target is exactly the configured private sandbox.

`dev-platform/live-sandbox/sandbox.toml` names the sandbox and its App. That is operator identity, so the file stays out of public snapshots and the runner works only from the operator checkout.

The sandbox differs from production in two ways. The repository admin may write main directly, because the runner commits the baseline that way. Its queue and worker workflows also request Checks read and Actions read: `token_read_permissions` in `dev-platform/live-sandbox/sandbox.toml` lists them and the runner adds them to each App token step of the snapshot. Without either one the queue does not see the required check of a private repository: a run without Actions read escalated with `validate` not reported, although failed job logs are read by the operator's `gh`. The production token on the public repository keeps contents and pull requests write only. The gh login's REST budget is shared with real deliveries.

## Owner setup

Done once, by the owner:

1. Create the GitHub App with Contents, Pull requests and Workflows write, Metadata, Issues, Checks and Actions read.
2. Install it only on the sandbox.
3. Set `DEV_PLATFORM_APP_CLIENT_ID` and the secret `DEV_PLATFORM_APP_PRIVATE_KEY` on the sandbox. `DEV_PLATFORM_APP_CLIENT_ID` takes the numeric App id: the queue and worker workflows pass it to `app-id`.

A missing secret or variable stops the runner with its name. After each reset the runner runs the queue once, so an App lacking a requested permission stops the run with the failed step.

## Running

```bash
python3 scripts/live_scenarios.py run --workdir <directory> [--head <commit>] [--scenario <name>]
python3 scripts/live_scenarios.py reset --workdir <directory>
```

`--workdir` is owned by the runner and its content is replaced. A directory that is not empty and was not created by the runner is refused.

Runs happen on the operator Mac: repair, composition finalize and post-merge jobs exist only there. No LaunchAgent or machine configuration is involved.

Each run starts with a reset, so a failed run is not inherited: open PRs and Issues are closed, work branches are deleted and the baseline is committed forward. History is not rewritten. Queue state lives in comments of closed PRs, and new PRs get new numbers. One run holds the sandbox at a time through the `LIVE_SCENARIO_LOCK` Actions variable; a lease that expired belongs to a dead run and is taken over.

## Scenarios

| Scenario | Path on real GitHub |
| --- | --- |
| `quick-task` | Quick task, queue, MERGED by the sandbox App. |
| `managed-task` | Managed Issue, start, developer handoff, review, hosted finalize with the real archive and `openspec validate`, queue, MERGED. |
| `red-ci` | Required CI fails only on GitHub through `fixture/ci-verdict.txt`, the queue offers integration repair, the operator reads the failed log, the repaired head merges. |
| `conflict` | After admission the runner moves main with a conflicting commit, the queue offers integration repair, the repaired head merges. |
| `requirement` | Pre-authoring chain, two children through contributions, main moves and `absorb-main` runs between them, composition review, local finalize with full checks and real `npx`, queue MERGED, post-merge with late friction, terminal closes the sandbox Requirement. |
| `contribution-conflict` | Two children run in parallel, the first merges into the requirement branch, the queue offers integration repair of the second, the repaired head passes review again and merges. |

The model is scripted, GitHub is not. `dev-platform/live-sandbox/executors/` holds a reviewer behind `DEV_PLATFORM_CLAUDE_BIN` and a repair writer behind `--llm-command`, so a finding or repair reproduces on every run and no provider token is needed. A real model, the sandboxed writer and hosted review are outside these scenarios.

## Handoff gate

`dev-platform/live-scenario-gate.toml` declares the queue and lifecycle paths, the scenarios a receipt must hold and the known failures. `run` writes a receipt to `.claude/live-scenario-receipts/` of the integration checkout, bound to the declared paths at the tested head. Commits outside those paths keep it; a merge or fix that changes them needs a new run.

`dogfood_task.py finish` refuses a change touching a declared path when the receipt is missing, lacks a scenario or holds a red scenario that is not a known failure. A known failure is printed with its defect and does not block. An unavailable sandbox stops the runner, so there is no receipt and the handoff stays refused; the coordinator resolves that.

Run the scenarios on the commit you hand off: `run --workdir <directory>`, without `--scenario`. A partial run writes no receipt.

## Cost

Measured on one full run of four scenarios: 16 minutes of wall time, 79 Actions runs, about 38 minutes of runner time, of which the fixture CI is under 2. Most runs are queue and worker wake-ups that find nothing to do. Scenarios run one after another, each about 4 minutes; `managed-task` and `red-ci` are the longest. No model tokens are spent. Runs need Actions minutes of the private repository. No shorter set is defined: a full run fits the gate at this duration.

## Coverage

Items that recent delivery reports left unverified on live GitHub. This is a map, not a backlog: a found defect is filed on its own.

| Item | Source | Status |
| --- | --- | --- |
| Hosted queue run of integration repair | `conflicting-candidate-integration-repair`, `receipt-main-only-integration` | `conflict`, `red-ci`, `contribution-conflict` |
| Target ref of `select_checks.py` and `finish_task.py` on a contribution | `contribution-integration-contract` | `requirement`, `contribution-conflict` |
| `RequiredChecksWait` in `work-next` | `contribution-integration-contract` | `requirement`, `contribution-conflict`, when a worker meets running checks; not forced |
| Live contribution path and its queue side | `contribution-integration-contract` | `requirement`, `contribution-conflict` |
| Live terminal job | `terminal-direct-lineage` | `requirement` |
| Retrospective refresh after late friction | `requirement-retrospective-refresh` | `requirement` |
| Owner-declared sequential Requirement | `sequential-child-delivery` | Not covered: `requirement` delivers children in turn but declares no sequence |
| Post-merge finish of a merged contribution | `merged-finish-reconcile` | Not covered: no scenario calls it, since post-merge jobs carry a handed-off contribution |
| `npx` in composition full checks | BR acceptance | `requirement`, through the archive rehearsal |
| Older installed `pre-merge-commit` hook | `contribution-integration-contract` | Not covered: the sandbox checkout always installs the current hook |
| Deleted child context of a contribution | `contribution-integration-contract` | Not covered: reported follow-up, needs a broken checkout |
| Exhausted retrospective refresh | `requirement-retrospective-refresh` | Not covered: no scenario spends the attempts |
| Main merge touching a child's task path under a Requirement | `receipt-main-only-integration` | Not covered: `absorb-main` here moves an unrelated path |
| Hosted refusal of composition finalize | composition dead-end report | Not asserted: the hosted class runs during `requirement` but the scenario reads no refusal |
| Failed full checks of a composition and `resume` on finalize | composition dead-end report | Not covered: resuming it is a known dead end, filed as a defect |
| Red CI on a composition with enqueue | composition dead-end report | Not covered: no scenario fails CI there |
| Portable developer archive | `archive-finalize-function` | Not covered: the sandbox runs in source mode |
| Leftover state in a standalone downstream checkout | `sequential-child-housekeeping` | Not covered: downstream checkouts are outside the sandbox |
| `close-abandoned-delegation`, `route-codex` output, other users' processes through `lsof` | `delegation-abandon-recovery` | Not covered: Codex only, and Codex scenarios are excluded |

## Results

The runner acts as developer and coordinator through documented entrypoints only. A manual step is any action outside them, such as editing a label or a lifecycle comment. A failed or timed-out step exits non-zero, naming scenario, step and observed state.
