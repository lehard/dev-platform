OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the chat-coordinator delta (renamed and modified role requirement), proposal, design and tasks; openspec validate --strict; targeted unit tests (test_lifecycle_overview incl. the new post-merge hint test); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Direct handoff (deterministic depth, no ADD): the owner fixed the role and its limits on 2026-10-28 (variant A).
- The role requirement is renamed (observer and exception operator -> delivery orchestrator) and rewritten, so the accepted spec no longer forbids routine coordinator runs.
- The post-merge `unclaimed-next-job` hint is computed from the job kind, repository and PR; other kinds keep their existing hint.

## Completeness

- Review repair (head 36a17164): the accepted "Operator decisions are head-bound and attributed" required an explicit owner decision naming the PR for every `resume`/`switch-provider`, contradicting the orchestrator role. The delta now MODIFIES it: routine technical recovery needs no per-PR owner decision; material findings, exhausted rounds and disputed rejections or dispositions still do; `--expected-head`, attribution, no claim bypass and truthful reporting unchanged; both scenarios kept (the head-change scenario now names the coordinator or user). Semantically checked against the role requirement, `docs/engineering/chat-coordinator.md` *Authority* and *Rules*, and the overview eligibility function (unchanged): consistent.

- Role, authority, owner decisions, red lines and the new-session scenario: chat-coordinator delta; `docs/engineering/chat-coordinator.md` sections *Authority* and *Delivery cycle (runbook)* (commands with GH_TOKEN and CLAUDE_CODE_OAUTH_TOKEN, main freeze, handover, cadence); the exception *Rules* no longer require a per-PR owner message for technical recovery.
- `AGENTS.md` concern row names the orchestrator role and runbook.
- Overview hint for an unclaimed post-merge job names the runner and `GH_TOKEN="$(gh auth token)" python3 scripts/lifecycle_workers.py work-next --repo <repo> --kinds <kind> --pr <N> --run`: `test_unclaimed_post_merge_job_names_the_runner_and_the_exact_local_command`; the review-job hint is unchanged (`test_overdue_claim_findings_say_a_worker_is_needed_not_a_human_decision`).
- `agent-workflow.md`: hosted kinds review, finalize and integration-merge match `hosted_workers.CLASSES`; the `finalize-pending` re-handoff (BR-933) replaces the stale "not re-admitted" sentence.

## Correctness

- No authority widening: material findings, exhausted rounds, disputed rejections, business and OpenSpec decisions stay with the owner; the overview eligibility function is unchanged.
- No code path beyond the hint text changed.

## Coherence

- Spec delta, docs, design and tasks describe the same role; the platform manifest is regenerated.

## Not verified / limits

- The capability `## Purpose` still says recovery commands run "after an explicit owner decision". OpenSpec reads a delta Purpose only when it creates a capability, so an existing capability's Purpose has no supported delta path; it is left unchanged and reported as a follow-up instead of editing the accepted spec outside archive.

- The "new session reconstructs state from the runbook alone" scenario is a documentation property, not exercised by a test.
