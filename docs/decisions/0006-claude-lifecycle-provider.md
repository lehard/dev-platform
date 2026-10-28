# DEC-0006: Claude as the provider for review, repair and finalize

- **Status:** Current
- **Scope:** Lifecycle jobs of the central platform (review, repair, integration-repair, finalize)
- **Decision date:** 2026-10-11
- **Authored against revision:** `e8392062178fa6b5e3ed7eabd66b8bfa54b2c70e`
- **Supersedes:** None
- **Superseded by:** None

## Accepted current decision

From 2026-10-11 the platform's own review, repair and finalize jobs run on Claude instead of Codex. Jobs
that were already running on Codex were finished first and switched afterwards, so no work was lost; a
running job is never aborted only to change its provider.

In practice:

- hosted review on GitHub Actions passes `--providers claude` (`.github/workflows/lifecycle-workers.yml`);
- a candidate that still records Codex is moved with
  `python3 scripts/publication_queue.py switch-provider --provider claude ...`, and the switch persists
  for later repair rounds and re-reviews;
- a quick task or Requirement composition without a developer route records the default route
  `claude`/`standard` (R2) on its first repair job (BR-768, variant A).

## Rejected and deferred alternatives

- Keeping Codex for repair was rejected: the owner prefers one provider for the whole platform lifecycle,
  and an earlier "repair on Codex" instruction is superseded by this decision.
- Removing Codex support from code and central configuration is deferred: `agent_tools = "claude,codex"`
  and `[model_routing.codex]` stay in `.dev-platform.toml` and are tracked by BR-852. Downstream projects
  keep the provider choice the template offers them.

## Evidence

- The hosted review worker in `lifecycle-workers.yml` installs Claude Code and claims only review jobs offered to the `claude` provider.
- `publication_queue.py switch-provider` records the provider per job kind on the candidate, so later
  rounds follow it (see [agent-workflow.md](../engineering/agent-workflow.md)).

## Revisit triggers

- Claude review or repair quality, availability or cost regresses materially against another provider on
  the platform's own candidates.
- BR-852 removes Codex from central configuration, or a downstream project requires Codex for its own
  lifecycle.
