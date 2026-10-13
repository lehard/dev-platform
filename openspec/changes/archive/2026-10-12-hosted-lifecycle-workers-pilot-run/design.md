## Context

`lifecycle-workers.yml` is `workflow_dispatch`-only. The queue workflow (`publication-queue.yml`, name *Dev Platform publication queue*) runs on `pull_request_target[labeled]`, a 5-minute schedule and dispatch, and publishes the head-bound jobs a hosted worker claims. `workflow_run` workflows always run the workflow file from the default branch, and the trigger fires for runs of the named workflow on any ref.

## Decisions

1. **Two triggers, both default-branch code.** `workflow_run: workflows: ["Dev Platform publication queue"], types: [completed]` starts a worker after the queue has had a chance to publish; `schedule: cron "*/10 * * * *"` covers missed events and expired claims. `workflow_dispatch` stays for manual runs and diagnosis. The existing job guard (`github.ref == refs/heads/<default branch>`) holds for all three: scheduled and `workflow_run` runs execute on the default branch.
2. **No payload use.** The worker never reads `github.event.workflow_run.*`; a test pins that, so a PR-influenced value (branch name, title) cannot reach a step even though the triggering run may come from a pull request event.
3. **Overlap is already handled.** Per-class concurrency (`cancel-in-progress: false`) keeps at most one running and one pending run; claims are head-bound; the 25-minute timeout is below the 30-minute claim. A queue completion and a schedule tick at the same moment therefore queue rather than overlap.
4. **Run on every queue completion, regardless of conclusion.** A failed queue run may still have published jobs earlier; the worker is idempotent when nothing is claimable (`idle`, no provider call).
5. **Supported Node.** Install Node 22 (pinned exactly, `22.12.0`) for both classes; the finalize tools (OpenSpec 1.13.2) and the Claude CLI run on it. A test pins that the workflow's Node major satisfies the engine range `>=22`.
6. **`finalize` stays off.** The enabling variable remains `review`; enabling `finalize` is a separate owner decision because finalize runs candidate code beside a contents-write token.

## Risks and mitigations

- **Cost of unattended runs.** Every queue completion and 10-minute tick starts a runner. Idle runs do no provider call and finish in about a minute; the schedule can be removed independently of `workflow_run`. The pilot record (next child) states observed minutes and Claude usage.
- **Untrusted event influence.** `workflow_run` can be fired by PR-event runs; the guard, the no-payload rule, default-branch checkout with `persist-credentials: false` and the unchanged credential boundary keep PR-controlled values out of the token-holding steps.
- **Silent failure.** A red run is the visible signal: provider-unavailable, escalation and refusal outcomes fail the run with their cause.

## Provenance note

Package revision 2 of this change: scope narrowed from "run the pilot and record the decision" to "enable the triggers and fix the first-run findings"; recording the evidence and the placement decision moved to the separate change `hosted-lifecycle-workers-placement-decision`. The Issue body was aligned to this scope before this revision so the recorded source-Issue evidence matches it.
