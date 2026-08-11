## Context

`dev-platform` already has a local structured friction log and a central GitHub issue inbox, but the current path between them is intentionally manual. That protects raw evidence, yet it leaves capture and promotion dependent on agent memory and human follow-up. The platform also has no need to invent a local scheduler now that `gh-aw` can run Codex inside GitHub Actions on events and schedules with read-only analysis and validated safe outputs.

This design treats GitHub Issues as the visible process backlog and `gh-aw` as an external, replaceable automation layer. It does not make cloud agents part of deterministic build/test/release correctness.

## Goals

- Minimize human participation in process-problem capture and review.
- Reuse maintained GitHub automation rather than create a scheduler/daemon/background-agent subsystem.
- Keep the first version small enough to diagnose and trust.
- Preserve raw local evidence privacy and fail safely when GitHub/API access is unavailable.
- Prevent duplicate issue spam.
- Keep one explicit human decision before code-changing remediation.
- Make the cloud layer removable without breaking local development lifecycle.

## Non-Goals

- Autonomous code fixes, autonomous OpenSpec acceptance, autonomous PR merge, or self-modifying platform rules.
- Full `Repo Assist` adoption in v1.
- Managed-project rollout in this change.
- Replacing deterministic CI, lifecycle checks, release orchestration, or local containment.
- A local cron/launchd daemon.

## Decisions

### 1. GitHub Actions is the scheduler and runtime

Agentic maintenance runs in GitHub Actions through compiled `gh-aw` workflows. The source-of-intent remains Markdown under `.github/workflows/`; compiled lock workflows are committed as required by `gh-aw`.

The implementation SHALL select and record one exact tested `gh-aw` release rather than tracking `latest` implicitly. Updating that pin is an explicit maintenance action.

### 2. Codex is the initial engine

The pilot uses `engine: codex` and the repository Actions secret `OPENAI_API_KEY`. The secret is never committed, printed, copied into OpenSpec evidence, or exposed to the agent prompt.

### 3. Start with two narrow workflows

#### Process issue triage

Adapt the upstream `githubnext/agentics` issue-triage pattern rather than starting from an unrestricted general repository assistant.

The workflow runs only for issues that match platform/process routing criteria (for example a controlled label or title prefix). It may:

- inspect repository context and related issues;
- add allow-listed type/severity/status labels;
- identify likely duplicates;
- add at most one concise triage comment.

It may not edit repository contents, create implementation pull requests, merge, approve, or close issues in v1.

#### Process backlog review

Run on a weekly fuzzy schedule and via `workflow_dispatch`. It reviews the open process backlog and produces one concise current summary containing:

- new/unreviewed issues;
- likely duplicates;
- likely already-resolved/stale items;
- issues needing more evidence;
- issues ready for a human remediation decision.

The summary is advisory. It may update labels/comments and create/refresh a bounded summary issue, but it does not close source issues or start fixes in v1.

### 4. Cost and runaway protection are part of the contract

Every cloud agent workflow SHALL declare a bounded `timeout-minutes` and `max-ai-credits`. Initial values should be intentionally conservative and may be tuned only after reviewing a representative run with `gh aw audit`/`gh aw logs`.

The first implementation should prefer a per-run cap over a complicated daily accounting scheme. No scheduled workflow should run more frequently than needed for its user-facing purpose.

### 5. GitHub Issues become the visible backlog; local JSONL becomes raw/fallback storage

`agent_friction.py` remains useful, but its role changes:

- raw observation/evidence may stay local;
- a sanitized candidate contains scope, severity, observation, hypothesis/proposal summary and a stable fingerprint;
- routing attempts to create or update the appropriate GitHub issue automatically;
- `scope=project` routes to the current repository;
- `scope=platform` routes to the configured platform repository (`lehard/dev-platform` for current managed projects).

Manual `promote` is no longer the normal operator path.

### 6. Repeated friction updates one issue

A stable fingerprint is computed from normalized non-secret fields such as scope plus a machine-safe category/key. The corresponding issue contains a machine-readable marker such as an HTML comment. Before creating a new issue, routing searches for an open issue with that marker.

When found, the router adds a bounded sanitized occurrence comment or increments structured occurrence metadata rather than opening another issue.

The fingerprint must not include raw evidence, tokens, absolute secret-bearing paths, or arbitrary user content.

### 7. Capture is enforced at lifecycle boundaries

Machine-detectable lifecycle failures should call the friction recorder directly.

For model-observed friction, ordinary non-trivial completion includes a small mandatory checkpoint asking whether any high-signal condition occurred (user correction, repeated failure, safety near-miss, workaround, false task premise, avoidable CI/lifecycle failure, or excessive retries). If yes, a structured friction record must exist before completion reports success.

This checkpoint is implemented only after `durable-publication-recovery` stabilizes so the two changes do not race on `finish_task.py` semantics.

### 8. Routing failure is durable but does not break safe delivery

If GitHub authentication, API availability or network access prevents issue routing:

- retain the local pending event;
- report a concise non-secret warning;
- retry pending routing during a later supported doctor/start/finish invocation;
- do not silently drop the event;
- do not fail an otherwise safe code publication solely because process telemetry could not be uploaded.

### 9. Human approval remains before remediation

The cloud review may recommend `ready-for-fix`, but v1 has no trigger that writes code from that status. The operator approves remediation explicitly; normal OpenSpec/task lifecycle then performs the implementation.

This keeps autonomous observation and triage separate from autonomous self-modification.

### 10. The cloud layer is additive and replaceable

`gh-aw` workflows must not become prerequisites for deterministic CI or release correctness. If `gh-aw`, OpenAI API, or GitHub Actions is unavailable, local development and publication continue; only automated process triage/review is degraded.

## Rollout Strategy

1. Merge this OpenSpec plan only.
2. Implement and validate the cloud workflows in `dev-platform` independently of `finish_task` work.
3. After `durable-publication-recovery` stabilizes, integrate automatic friction checkpoint/routing with the final lifecycle shape.
4. Run one manual workflow dispatch and one real issue-event triage acceptance.
5. Let at least one scheduled review complete successfully and inspect cost/audit output.
6. Archive/release this central-platform change only after those acceptance checks pass.
7. Create a separate follow-up OpenSpec for managed-project rollout if the pilot is stable and useful.

## Risks and Mitigations

- **Public Preview churn:** pin an exact tested `gh-aw` release and validate compiled workflows in CI.
- **Prompt injection through issue text:** keep agent jobs read-only and use allow-listed `safe-outputs` only.
- **Unexpected spend:** conservative `max-ai-credits` and timeout, low-frequency schedule, audit representative runs.
- **Issue spam:** stable fingerprint deduplication and bounded safe outputs.
- **Cloud outage/vendor change:** keep the layer additive; local lifecycle must not depend on it.
- **Concurrent lifecycle work:** delay `finish_task` integration until `durable-publication-recovery` is stable.
