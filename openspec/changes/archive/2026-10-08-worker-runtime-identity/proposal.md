## Why

Three independent defects let the lifecycle misattribute or mis-run work.

- `lifecycle_workers.main` defaults `--worker` to `DEV_PLATFORM_WORKER` or `worker-<pid>`. Two hosts (or a restarted worker that reuses a PID) produce the same claim identity, and `i_won` compares only that string, so one worker can believe it won another worker's claim. `execute_job`, `run_claimed` and `run_claimed_integration_repair` additionally default `worker="worker"`, a constant shared by every caller.
- Repair provider selection is not tied to the originating task. `publication_queue.publish_job` resolves the provider from the coordinator checkout's current route or `[independent_review]` configuration, and when that is unknowable it publishes the literal `unresolved-originating-task-route`, emits a "falls back to the default provider" friction event and proceeds. Coordinator-side repair publication (`required-checks` repair, `integration-repair`) never passes providers at all. The worker never compares the job's providers with the executor behind `--llm-command`.
- `requirement_integration._run_full_checks` runs repository-owned `full_commands` with `credential_free_env` and a scratch HOME. That is correct for LLM and harness Git, but it strips the HOME-resident Docker, uv and application credentials that downstream projects such as kamenkadmitry/ai_assist_content need, so their application checks cannot run in the coordinator.

## What Changes

- Add one worker identity contract in `lifecycle_workers.py`: a validated explicit identity (flag, then `DEV_PLATFORM_WORKER`), otherwise a generated host-pid-nonce identity; resolved once per run; required (no library default) everywhere a claim or result is written.
- Record the originating task route (provider, change) on the handoff record when the developer checkout admits the candidate, and resolve every later review, repair and integration-repair job provider from that record. Remove the `unresolved-originating-task-route` sentinel and the fallback friction path; a missing or contradictory route raises.
- Add `work-next --provider`, require it for repair and integration-repair kinds, and claim only jobs whose recorded route provider matches. The claim and result records carry the provider.
- Add a `project-check` environment purpose beside the existing LLM and harness-Git purposes: declared `[runtime]` requirements in `dev-platform/checks.toml`, validated against the machine, with operator-granted home paths from a machine-local grant file outside any checkout. `_run_full_checks` uses it. LLM and harness Git environments are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lifecycle-workers`: unique validated worker identity, provider-authorized repair claims, and the purpose-specific environment contract for trusted project checks.
- `publication-queue`: handoff records persist the originating task route; job publication inherits it and fails when it is missing or contradictory.

## Impact

Platform-owned `template/scripts/lifecycle_workers.py`, `template/scripts/requirement_integration.py`, the job/handoff path of `template/scripts/publication_queue.py`, `template/scripts/pr_review_gate.py`, `template/scripts/integration_contour.py`, an additive route field in `template/scripts/candidate_lifecycle.py`, a read helper in `template/scripts/model_routing.py`, the `scripts/` shims where they enumerate options, and their regression tests. Downstream projects that declare no `[runtime]` table keep today's isolated check environment. Candidates already admitted without a recorded route cannot receive repair jobs until re-handed-off; this is an explicit failure, not a fallback.

## Success Criteria

Two workers launched on different hosts or with the same PID never share a claim identity; an invalid explicit identity exits non-zero. A repair job is only offered to and claimed by a worker serving the originating route's provider (or the provider an operator re-offer recorded for the job), and its job, claim and result records show that provider. A project that declares Docker/uv and a granted home path passes its checks in the coordinator, a project with an unmet declaration fails naming the missing input, and no LLM or harness Git environment gains a credential or a real HOME.

## Non-goals

Comment/check/trust reading changes (publication-observation), independent pre-release Requirements, stable tagging, fleet rollout, remote reviewer, TeamAI and economy routing. No change to review provider ordering configured through `[independent_review] providers`. No hardening of the broader ambient environment already forwarded to project checks beyond what this design states.
