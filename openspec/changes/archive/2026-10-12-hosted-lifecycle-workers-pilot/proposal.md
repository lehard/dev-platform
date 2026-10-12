## Why

BR-610: the platform already persists durable head-bound jobs, claims/results, bounded review and repair, finalize, the integration queue and post-merge reconciliation. After a developer handoff, however, those jobs are executed only if somebody runs `lifecycle_workers.py work-next` — a running Codex/Claude session or the owner. The only GitHub-hosted worker today is the publication queue, which publishes and integrates; a successful run that reports `waiting` is not progress, and a candidate with an unclaimed review job waits indefinitely.

## What Changes

Current: jobs are published; execution depends on an operator-run worker; `publication-queue.yml` is the only hosted lifecycle automation and holds the only App token.

Target: one new workflow runs the existing worker command on GitHub-hosted runners for explicitly enabled, evidence-proven job kinds, using the same claim/result contract, trust model and harness as a local worker.

- Add `.github/workflows/lifecycle-workers.yml`: shipped with `workflow_dispatch` only (no cron, no `workflow_run`); executes only default-branch code; a keyless `plan` job turns the required enablement variable into a matrix of job-kind classes; each class job mints a GitHub App token limited to the rights of its class, runs a repository-owned hosted preflight, then one `work-next --run` for that class with a unique `gha-` worker identity. This slice hosts two classes: `review` (kind `review`) and `finalize` (kind `finalize`), both with pull-request and contents write because the harness pushes review evidence and the finalization commit. `repair` and `integration-repair` (no platform-supported hosted writer exists until BR-576) and the post-merge kinds `retrospective`, `terminal-reconciliation` and `cleanup` (they need machine-local lifecycle state and Development Backlog access that a runner does not have) are refused by name with that basis and stay on the local operator node (BR-433).
- Add the repository-owned `hosted-preflight` command to `lifecycle_workers.py` (template implementation, source adapter unchanged): proves the class, the Claude runtime and its provider secret through the existing readiness probe, the credential-free child environment, and the token scope, stopping at the first failure with a named, secret-free diagnostic.
- Make hosted outcomes concrete: an idle run, a claimed job and its result, an unavailable provider and a refused or failed run are distinct printed outcomes and run conclusions; none is reported as `Done`.
- Add `docs/engineering/hosted-lifecycle-workers.md`: the owner's enablement instruction (provider secret, App variables, `DEV_PLATFORM_HOSTED_KINDS`, then adding the `workflow_run` and `schedule` triggers in a reviewed change), the constraints to verify (hosted vs minimal local fallback), operating and rollback notes; point `docs/engineering/agent-workflow.md` to it.
- The real-PR pilot and the recorded placement decision are NOT part of this change: they need owner-provisioned credentials and are the next BR-610 slice.

## Capabilities

### Modified Capabilities

- `lifecycle-workers`: new requirements for hosted placement, evidence-gated enablement, concrete hosted outcomes, duplicate/restart safety of hosted triggers and the pilot decision.

## Success evidence

- Everything is verifiable without owner action: the workflow structure tests, the hosted-preflight tests (each missing/contradictory input — class, unhosted kind, enabling variable, provider secret flag, runtime probe, credential leak, token scope — fails naming the input and prints no secret) and the behavior tests with the existing fakes (idle, unavailable provider, overlapping claims, expired claim, moved head, advanced `main`, no merge request).
- The workflow, run by hand without its required configuration, fails explicitly naming the missing variable; it has no automatic trigger.
- The enablement document lets the owner turn the hosted worker on, one class at a time, and turn it off again, without reading code.
- Not claimed by this change: that a hosted run reviewed or merged a real PR. That evidence belongs to the pilot slice.

## Impact

`.github/workflows/lifecycle-workers.yml` (new), `template/scripts/lifecycle_workers.py` (+ the unchanged source adapter), `docs/engineering/hosted-lifecycle-workers.md` (new), `docs/engineering/agent-workflow.md`, tests; GitHub repository secret/variables (owner-provisioned later, outside the diff). No change to job, claim, result or marker formats, to review/repair/finalize logic, to the publication queue workflow or merge authority, or to downstream templates.

## Non-goals

Second queue/state machine/state store; permanent coordinator session; moving any stage to CI whose prerequisites are not proven; local-worker merge rights or any change to the BR-575 CI-only merge protocol; rewriting the Claude isolation contract (BR-576) or review/repair/finalize; downstream rollout; operator chat surface (BR-611); building the BR-433 node.
