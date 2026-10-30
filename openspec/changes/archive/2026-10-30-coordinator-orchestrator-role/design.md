## Context

`lifecycle_overview.py` maps each finding kind to a static hint (`FINDING_HINTS`); `unclaimed-next-job` says "a lifecycle worker (hosted run or local node) has to claim the job". Post-merge kinds (retrospective, terminal-reconciliation, cleanup) are never hosted (`hosted_workers.UNHOSTED`); since BR-885 the LaunchAgent `post_merge_runner.py` runs `lifecycle_workers.py work-next --kinds retrospective,terminal-reconciliation,cleanup --run` every 10 minutes from the integration checkout. `work-next --pr N` reads one PR directly.

## Decisions

- **Spec text over side agreement.** The role requirement is modified, not supplemented, so the accepted spec no longer forbids routine coordinator runs (owner rejected variant B).
- **Authority split.** Routine recovery after a technical failure (`resume`, `switch-provider`, `reoffer-post-merge`, `restore-gates`) needs no owner message; material findings, exhausted review/repair rounds, disputed rejections, business and OpenSpec decisions still go to the owner with options, cost/risk and a recommendation. Where an executor's contract needs the owner's own words, the coordinator asks the owner and never supplies wording.
- **Post-merge hint is computed from the job.** For an `unclaimed-next-job` finding whose job kind is a post-merge kind, the hint names the post-merge runner and `GH_TOKEN="$(gh auth token)" python3 scripts/lifecycle_workers.py work-next --repo <repo> --kinds <kind> --pr <N> --run` from the integration checkout; other kinds keep the existing hint.
- **Runbook cadence.** Event-driven (session notes, job completion, CI); a rare heartbeat; concrete intervals written in the runbook.

## Risks

- A coordinator over-reading "routine" could act on a finding-level escalation; the spec and runbook list those as owner decisions and the overview eligibility function already refuses `resume` for them.
