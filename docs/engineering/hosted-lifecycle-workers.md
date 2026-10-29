# GitHub-hosted lifecycle workers (BR-610)

After a developer handoff the coordinator publishes head-bound jobs, and a worker must claim them. The hosted worker runs the existing `lifecycle_workers.py work-next --run` contract on a GitHub-hosted runner, so a published review or finalize job no longer waits for a running Codex/Claude session or for the owner. It adds a placement, not a second queue or state store: claims, results, trust, exact-head discard and the harness-only push are unchanged, and merging stays with the publication queue.

This document is the owner's enablement instruction and the record of the pilot. The workflow `.github/workflows/lifecycle-workers.yml` has three triggers: manual `workflow_dispatch`, `workflow_run` on completion of the *Dev Platform publication queue* workflow, and a `schedule` of every 10 minutes as a backstop for missed events. All run the default-branch workflow under the same default-branch guard, and no step reads the triggering event's payload. A run still fails explicitly until the owner has completed enablement steps 1-4 below.

## What runs hosted and what does not

| Class | Kind | Provider | Runner tooling |
| --- | --- | --- | --- |
| `review` | `review` | Claude (headless, read-only tool allowlist) | pinned `@anthropic-ai/claude-code` |
| `finalize` | `finalize` | none | pinned OpenSpec, Ruff, Jinja2, Copier |
| `integrate` | `integration-merge` | none | none |

Every class uses a GitHub App token for this repository with pull-requests write and contents write, because the harness posts the claim/result comments and pushes the review evidence, the finalization commit or the integration-merge commit to the candidate branch (expected-head guarded, never force, never `main`). The hosted worker issues no merge request.

These kinds are refused by name and stay on the local operator node (BR-433):

- `repair`, `integration-repair`: a writer holds a shell and the provider token, and no platform-supported hosted writer with proven containment exists yet (the sandboxed Claude writer is BR-576). No writer starts automatically: the queue posts a "Repair needed: PR #N" attention comment with the reason and the `work-next --kinds <kind> --writer claude-sandboxed --run` command, and an operator runs it (BR-768).
- `retrospective`, `terminal-reconciliation`, `cleanup`: they read machine-local lifecycle state (friction log, retrospective checkpoints) and Development Backlog Issues that a runner token cannot reach.

A review job whose providers do not include `claude` is not picked up by the hosted worker; switch it with the operator re-offer command.

## Enablement, in order

1. **Provider secret.** Create a dedicated, revocable, usage-capped Claude token for this repository only (`claude setup-token`) and store it as the repository secret `CLAUDE_CODE_OAUTH_TOKEN`. An agent never enters or reads it. Do not reuse a personal token.
2. **App configuration.** The workflow reuses the publication queue's repository variable `DEV_PLATFORM_APP_CLIENT_ID` and secret `DEV_PLATFORM_APP_PRIVATE_KEY`; they are already present when the queue runs.
3. **Enabling setting.** Set the repository variable `DEV_PLATFORM_HOSTED_KINDS` to the kinds to host, starting with `review` (`review`, `finalize` or `review,finalize`). It is required: when the workflow runs and the variable is empty, the run fails naming it. An unknown kind fails naming it, and a refused kind fails naming the reason above.
4. **Manual run.** Dispatch *Dev Platform lifecycle workers* from `main`. Read each class job: the inputs and runtime preflight list every check, and the first failing check names the missing or contradictory input. A passing run on an empty queue prints the `idle` outcome in the job summary.
5. **Automatic triggers.** The triggers are part of the workflow; to turn automatic starting off, remove the `workflow_run` and `schedule` triggers in a reviewed change. The structure tests pin the allowed trigger set (`workflow_dispatch`, `workflow_run`, `schedule`); `pull_request` and `pull_request_target` are never allowed.

**Rollback.** Remove the `workflow_run` and `schedule` triggers, which leaves manual dispatch only (and, if wanted, clear `DEV_PLATFORM_HOSTED_KINDS`, which makes any manual run fail explicitly). Revoke the provider token if it should no longer exist. Local workers and the publication queue are unaffected.

## First manual run

Run 38221555792 on `main` passed the inputs and runtime preflight, including the Claude readiness probe, and reported `idle`. It exposed that the pinned Claude CLI needs Node 22 (`engines: node >=22`) while the workflow installed Node 20.19.0; this change installs Node 22.12.0 for both classes and a structure test pins a Node major of at least 22.

## What the preflight proves before a worker starts

`python3 scripts/lifecycle_workers.py hosted-preflight --mode ci --class <review|finalize|integrate> --phase inputs|runtime|all` stops at the first failed check, exits non-zero, prints no credential value and substitutes nothing:

- the class and the enabled kinds, the worker identity (`gha-<run_id>-<run_attempt>-<class>`, equal in the workflow and in the preflight);
- presence flags only for the App variable/key and the provider secret;
- the publication queue's coordinator preflight (App identity, trust configuration, installation token scoped to exactly this repository);
- required tools on the runner (`openspec` for finalize);
- the credential boundary: a child started through the same credential-free environment an LLM or check process gets sees no GitHub/App variable, askpass helper, SSH agent, credential-helper configuration or `gh` configuration;
- for `review`, the Claude readiness probe in the scratch environment a job would use.

The workflow runs only default-branch code, never checks out or executes pull-request content while a token is held (the worker harness fetches the PR head into a disposable credential-free checkout), requests no `workflows`, `administration`, `actions` or `id-token` scope, serialises runs per class without cancelling a running worker, and has a job timeout (25 minutes) below the claim lifetime (30 minutes).

## Outcomes

Each run prints one outcome in the job summary: `idle`; `job-reviewed`, `job-reused`, `job-finalized`, `job-returned-to-review` (this run published its result); `job-discarded`, `abandoned-lost`, `abandoned-stale` (the head or claim changed, so nothing was published for it); and the red ones `provider-unavailable`, `job-blocked-retryable`, `job-blocked-escalation`, `refused-or-failed` with their cause. A green run never means a candidate or Requirement is done; that is established by the exact merged PR and the post-merge receipts.

## Friction attribution and own pushes

A review or repair job derives its friction attribution before the reviewer or writer starts: the public work identity of the managed branch (`agent/br-N-tM-<change>` is `BR-N/TM` of `BR-N`, `requirement/BR-N` is `BR-N`). The coordinator evidence record on the PR stores only that identity, so the runner needs no Development Backlog configuration and no private Backlog reference reaches the public PR; the Requirement retrospective matches records by it. A managed-looking branch with a malformed identity fails the run (`refused-or-failed`) before any push.

After its own lease-protected evidence push a worker waits up to 60 seconds for the PR API to report the pushed head. A different head or a changed claim still discards the job; a head that never converges fails the run with that cause. Gates bound to unchanged task content survive the harness's own evidence push, including when an interrupted run is recovered from its `validated-push` receipt.

## Pilot record (2026-10-19 to 2026-10-22)

The automatic triggers have been on `main` since 2026-10-13. `DEV_PLATFORM_HOSTED_KINDS` was `review` during the period below and has been `review,finalize` since 2026-10-22. The record below comes from the claim/result comments on real pull requests and from the job summaries of every non-cancelled run of the workflow created from 2026-10-19 to 2026-10-22 06:40 UTC (306 runs). No synthetic job was created. `finalize` was not enabled, so everything below is about `review`.

### Real PRs reviewed after the developer session ended

In each case the developer session ended at its handoff (queue `admit`), the `workflow_run` trigger started the worker, and nobody ran a command. The worker claimed the job as `gha-<run_id>-1-review` and published `validated-push` and `reviewed` results under the App identity. A local worker then finalized the candidate and the publication queue merged it.

| PR | Handoff (`admit`) | Hosted claim | Run | Result |
| --- | --- | --- | --- | --- |
| #668 | 2026-10-20 23:56:50 | 23:57:42 | 39518284656 | `reviewed`, evidence pushed, merged |
| #669 | 2026-10-21 00:13:00 | 00:13:57 | 39519980583 | `reviewed`, evidence pushed |
| #669 (re-handoff) | 2026-10-21 09:09:53 | 09:10:53 | 39574875517 | `reviewed`, evidence pushed, merged |
| #687 | 2026-10-22 00:26:28 | 00:27:06 | 39699692512 | `reviewed`, evidence pushed, merged |

The hosted worker also reviewed #613, #614, #619, #629, #631, #635, #636, #637, #639, #644, #649 and #656 (19 `job-reviewed` runs in total).

### Observed constraints for `review`

- **Runtime and credentials.** The pinned Claude CLI on Node 22.12.0 and the repository's provider secret worked on every run that reached the work step. No `provider-unavailable` outcome was observed.
- **Credential boundary and workspace.** The runtime preflight, including the credential-free child check, passed on every run that reached the work step. No run failed on the reviewer's before/after workspace check: all 15 failures have the causes listed below.
- **Duration.** From handoff to hosted claim: 38-60 seconds. The `work` job of the 19 reviewing runs took 66-147 seconds (median 97). The whole run took 79-214 seconds, except one that waited about 30 minutes in the per-class concurrency group before it started. No run reached the 25-minute timeout.
- **Cost and rate limits.** Unobserved. The provider token is a subscription OAuth token and the runner reports no per-job usage, so there is no per-job cost to record. No rate-limit response was observed.
- **Trigger volume.** The `workflow_run` trigger started all 19 reviews. The 10-minute `schedule` fired only 5-8 times a day (GitHub throttles scheduled workflows), so it is a weak backstop. 58 runs were `cancelled`: a burst of queue completions superseded the pending `work` job in the per-class concurrency group. A running worker was never cancelled.
- **Duplicate claim.** On #668 the hosted worker and a local worker claimed the same job one second apart (23:57:42 and 23:57:43). The first claim won, only the hosted worker published a result and the local worker published nothing.
- **Moved head.** Five runs ended `job-discarded` (#619 three times, #629, #637) because the head or claim changed during the job. No result was published for them.
- **Expired claim.** On #628 (a Requirement composition PR, `requirement/BR-576`) ten hosted runs from 2026-10-20 06:17 to 12:46 claimed the same review job and failed. Each claim held the job until it expired after 30 minutes, then the next run claimed it again. A local worker reviewed it at 13:19. The expiry worked as designed, but the job was delayed about seven hours.
- **Advanced `main`.** `main` did not advance while a hosted job was running. When `main` advanced between rounds (#669), integration repair ran on the local node and the next review round was a new job.
- **Failures.** All 15 failed runs exited `refused-or-failed` with a named cause and published nothing:
  - five (#619 and #637, 2026-10-19 and 2026-10-20 03:10-03:15): a review with findings could not record its friction because the runner has no Development Backlog configuration. #636 fixed this by deriving the public work identity before the reviewer starts, and the next two hosted reviews of #637 passed;
  - ten (#628): the composition review resolves the private parent Requirement through the Development Backlog, which neither the runner configuration nor the repository-scoped App token can reach. Since BR-767 a worker without a configured Development Backlog skips such a review before it claims it, so the job waits for the local worker without a hosted claim. A contribution-contract failure inside a composition review is posted as a `failed` result and escalates the candidate with the named cause instead of crashing the run and leaving the claim until it expires.

### Comparison with the minimal local fallback

| Constraint | Hosted `review` | Local worker on the operator node |
| --- | --- | --- |
| Starts without a running session | yes, `workflow_run` within a minute of the handoff | only while a local worker loop runs |
| Development Backlog and machine-local state | not reachable | reachable |
| Composition (`requirement/BR-N`) review of a private Requirement | skipped before the claim | works |
| Credential boundary | proven by the preflight on every run | the local boundary contract, unchanged |
| Merge authority | none; the queue merges | none; the CI-only protocol is unchanged |

## Placement decision

| Kind | Placement | Basis |
| --- | --- | --- |
| `review` | **Hosted** (`DEV_PLATFORM_HOSTED_KINDS=review`) for task and contribution PRs | The preflight passed and real PRs were reviewed after the session ended, with the constraints above. A Requirement composition review of a private Requirement stays on the local operator node (BR-433): the hosted worker has no Development Backlog and does not claim it. |
| `finalize` | **Hosted** (`DEV_PLATFORM_HOSTED_KINDS=review,finalize` since 2026-10-22) | It runs candidate code beside a contents-write token. It was not part of the evaluated period above; the local worker finalized every PR in that record. |
| `integration-merge` | **Hosted class `integrate` once the owner adds it to `DEV_PLATFORM_HOSTED_KINDS`** | The queue offers it when integration failed on the `integration` gate with a clean trial merge (typically a failed derived merge). The harness merges current main without any writer, provider secret or `--llm-command`; a conflict or red required check at execution fails it by name and the next attempt is a writer `integration-repair` (BR-768). |
| `repair`, `integration-repair` | **Local operator node (BR-433), run by an operator** | A writer holds a shell and the provider token, and no hosted writer with proven containment exists (BR-576). The queue escalates each repair round with a "Repair needed" attention comment; no writer starts automatically (BR-768). |
| `retrospective`, `terminal-reconciliation`, `cleanup` | **Local operator node (BR-433), scheduled on the operator Mac by `scripts/post_merge_runner.py` (BR-885)** | They read the friction log, retrospective checkpoints and Development Backlog Issues, which a runner token cannot reach. |

No kind moved to CI by default, and no local worker gained merge or `main` authority beyond the CI-only protocol.

## Post-merge runner on the operator Mac (BR-885)

`scripts/post_merge_runner.py` runs the three post-merge kinds on the operator Mac every 10 minutes (a LaunchAgent, `StartInterval` 600) through the existing `lifecycle_workers.py work-next --run`. A round repeats `work-next` until it reports `idle`, so the chain retrospective -> terminal-reconciliation -> cleanup catches up in one round. It has no queue or state of its own: claims, results, the attempt limit and the attention on a spent obligation (`post-merge-exhausted` in `lifecycle_overview.py` and on the merged PR) are the platform's.

A round stops at: `idle`; `--max-jobs` runs; `--max-seconds`; the first failed run (the next round retries it, and the platform attempt limit ends the retries); or a GitHub REST remainder below `--min-rest-remaining` (read from `gh api rate_limit`, which is not charged; a skip is journaled as `rest-low` and is not a failure). A second round started while one runs is journaled as skipped (`flock`). A round that started and never ended (reboot, kill) is journaled by the next round as `interrupted-previous-round`; its claim expires by the claim protocol. Every argument is required and a missing one fails the round.

The journal is `<journal-dir>/post-merge-runs.jsonl`; read it with `python3 scripts/post_merge_runner.py journal --journal-dir <dir> --last 50`.

Install and rollback are owner steps; nothing installs the agent automatically. Arguments below are the recommended values (`CHECKOUT` is the integration checkout):

```bash
mkdir -p ~/.local/state/dev-platform/post-merge
python3 scripts/post_merge_runner.py launchagent --install --repo lehard/dev-platform --checkout "$CHECKOUT" --journal-dir ~/.local/state/dev-platform/post-merge --gh "$(command -v gh)" --min-rest-remaining 1500 --max-jobs 12 --max-seconds 840 --claim-ttl 900
python3 scripts/post_merge_runner.py remove-launchagent
```

Use `launchagent --print` with the same arguments to review the plist first.
