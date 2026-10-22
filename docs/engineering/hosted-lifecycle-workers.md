# GitHub-hosted lifecycle workers (BR-610)

After a developer handoff the coordinator publishes head-bound jobs, and a worker must claim them. The hosted worker runs the existing `lifecycle_workers.py work-next --run` contract on a GitHub-hosted runner, so a published review or finalize job no longer waits for a running Codex/Claude session or for the owner. It adds a placement, not a second queue or state store: claims, results, trust, exact-head discard and the harness-only push are unchanged, and merging stays with the publication queue.

This document is the owner's enablement instruction. The workflow `.github/workflows/lifecycle-workers.yml` has three triggers: manual `workflow_dispatch`, `workflow_run` on completion of the *Dev Platform publication queue* workflow, and a `schedule` of every 10 minutes as a backstop for missed events. All run the default-branch workflow under the same default-branch guard, and no step reads the triggering event's payload. A run still fails explicitly until the owner has completed enablement steps 1-4 below.

## What runs hosted and what does not

| Class | Kind | Provider | Runner tooling |
| --- | --- | --- | --- |
| `review` | `review` | Claude (headless, read-only tool allowlist) | pinned `@anthropic-ai/claude-code` |
| `finalize` | `finalize` | none | pinned OpenSpec, Ruff, Jinja2, Copier |

Both classes use a GitHub App token for this repository with pull-requests write and contents write, because the harness posts the claim/result comments and pushes the review evidence or finalization commit to the candidate branch (expected-head guarded, never force, never `main`). The hosted worker issues no merge request.

These kinds are refused by name and stay on the local operator node (BR-433):

- `repair`, `integration-repair`: a writer holds a shell and the provider token, and no platform-supported hosted writer with proven containment exists yet (the sandboxed Claude writer is BR-576).
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

`python3 scripts/lifecycle_workers.py hosted-preflight --mode ci --class <review|finalize> --phase inputs|runtime|all` stops at the first failed check, exits non-zero, prints no credential value and substitutes nothing:

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

## What the pilot still has to verify

This change delivers the mechanism and its tests. The real-PR pilot and the per-kind placement decision are the next slice of BR-610 and need the credentials above. For each kind it records:

- the Claude runtime and credential working on a hosted runner, and the observed per-job duration, cost and rate limits;
- the credential-boundary proof on a real runner, and that the read-only reviewer left the workspace unchanged (the existing before/after check);
- behavior under a duplicate trigger, an expired claim, a moved head and an advanced `main`;
- failure behavior of provider, authentication, network and check errors;
- a comparison with the minimal local fallback, and for any kind that cannot be proven the basis for the local operator node (BR-433). No kind is moved to CI by default and no local worker gains merge authority beyond the CI-only protocol.
