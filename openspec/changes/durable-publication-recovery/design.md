## Context

See proposal.md. Today `finish_task.py` re-runs validation and delegates the entire PR lifecycle to `project_publish.py` in one foreground process. The only publication lock protects direct local integration, not PR publishing. `agent_doctor.py` can find inactive dirty/unmerged worktrees but has no concept of a validated, archived candidate awaiting automatic delivery. `_platform_common.github_cli_env` tests the inherited process environment first, so an invalid `GITHUB_TOKEN` can prevent use of an otherwise-valid local `gh` session.

The template must remain self-contained at runtime and support `light`, `standard`, and `multi-agent`; `harness_mode=project` remains authoritative for project-owned publication. Machine-local records must not be tracked or contain secrets.

## Goals / Non-Goals

**Goals:**

- Persist the smallest safe state necessary to resume automatic PR publication for exactly the validated commit.
- Provide idempotent `finish_task`/status/resume behavior with one publisher per candidate.
- Make doctor and generated instructions expose a sealed-but-unmerged candidate as delivery work, not merely hygiene noise.
- Strengthen authentication fallback and browser-QA discovery without introducing a new service or secret store.
- Deliver template changes through normal Copier render/update paths.

**Non-Goals:**

- Auto-publish dirty, uncommitted, stale, unvalidated, or manually reviewed work.
- Replace a project-owned harness or auto-merge managed platform rollout PRs.
- Persist GitHub tokens, scrape credentials, or prescribe host-specific browser paths.
- Guarantee that an external GitHub outage or failed required check will merge without agent repair.

## Decisions

### A sealed candidate is the only automatic-resume boundary

Add a reusable publication-state helper, backed by an ignored per-repository path (configured in `.dev-platform.toml`, defaulting below `.claude/`). `finish_task` writes a state record only after its current clean-worktree, OpenSpec lifecycle, remote-base and selected-check preconditions succeed. The record contains schema version, branch, candidate SHA, integration branch, publication and merge modes, phase, PR number/URL when known, timestamps, concise sanitized result and optional publisher lease metadata.

The resume flow repeats safety-sensitive checks, verifies that `HEAD` and the branch still equal the sealed SHA, and interrogates GitHub to find/reuse the PR. It does not trust a record as authorization to publish. The state is a recoverable cursor, not a source of truth for Git or GitHub.

Alternatives considered: recording every worktree as a candidate would make abandoned/incomplete work easy to publish accidentally; relying only on the agent board loses standard-profile tasks and cannot distinguish a validated candidate. Both are rejected.

### Split publication into durable phases with one end-to-end lease

Refactor the platform-owned PR flow into phase operations shared by `finish_task` and `project_publish`: `sealed`, `branch_pushed`, `pr_open`, `checks_waiting`, `merge_requested`, `merged`, and actionable `blocked`/`failed` states. Each successful remote boundary is written atomically before the next boundary. A non-blocking file lease, with PID/start time/expiry and stale-lease recovery, covers the entire automatic PR attempt; status never waits on the lease. Exit handling records a concise recoverable failure unless publication has already reached its terminal state.

Expose `finish_task --status` and `finish_task --resume` (exact CLI names confirmed during implementation) so agents and doctor can inspect/resume without rerunning a second publisher. Normal `finish_task` detects a matching unfinished sealed candidate and resumes it rather than revalidating/publishing from scratch. Existing no-state behavior stays compatible.

Alternatives considered: a daemon would outlive terminal streams but adds operational dependencies; a shared main lock is too narrow because it does not protect feature-branch/PR operations. A file lease and explicit invocation are deterministic and dependency-light.

### Authenticate each candidate environment independently

Change `github_cli_env` to try, without printing values: (1) inherited explicit token environment, (2) a sanitized environment with `GH_TOKEN` and `GITHUB_TOKEN` removed so an existing `gh auth login` credential can work, and (3) a temporary environment populated from an existing git credential helper. Return only an authenticated subprocess environment. Credential-derived variables live only in memory and no status output distinguishes values.

Alternatives considered: always removing environment tokens would disregard deliberate CI/automation credentials; stopping after the first failure is the current bug. Ordered independent validation retains explicit intent while allowing safe fallback.

### Completion reporting is policy-aware

For `harness_mode=platform`, doctor calls the publication status helper after normal Git checks. A recoverable automatic candidate becomes a high-signal actionable status containing only branch/SHA/phase and the resume command. `finish_task` performs multi-agent board cleanup only after the merged state (manual mode retains its current hand-off behavior). Generated AGENTS guidance makes automatic merge a terminal invariant while preserving the explicit block/report rule for failed checks or authentication.

For `harness_mode=project`, doctor does not inspect or alter publication records; it points to the repository-owned lifecycle. This avoids claiming cross-project control where the platform intentionally does not own it.

### Browser QA discovery is a bounded diagnostic fallback

Add a small documented/scriptable discovery helper used by browser-QA guidance: first use a configured executable if present, then detect supported system browsers and compatible Playwright cache entries, emitting an executable source/path only locally. Browser checks retain their existing project ownership; the platform does not add Playwright as a universal dependency. A failed managed-browser install alone is therefore not sufficient evidence that browser QA is unavailable.

## Risks / Trade-offs

- [Stale publication record/lease] → Verify branch SHA and remote PR state on every resume; expire leases conservatively and retain state for inspection.
- [An old branch becomes unsafe after sealing] → Re-run remote-base, lifecycle and SHA checks; refuse automatic resume on mismatch.
- [File-state corruption] → Atomic writes, schema validation, actionable fail-closed status, and rebuild from Git/GitHub rather than automatic deletion.
- [Authentication fallback selects an unexpected account] → Run `gh auth status` for each candidate, retain existing repository/protection preflight, and expose account identity only if already returned safely by `gh`.
- [Copier update conflict] → Treat the scripts/config/docs as platform-managed template content, exercise render/update tests, and use reviewed downstream rollout PRs.
- [Browser paths vary by OS] → Keep discovery generic/configurable and test with mocked executable discovery; do not commit absolute paths.

## Migration Plan

1. Add the state path/default and ignore coverage to the template, with absent state treated as no pending publication.
2. Implement state/lease/auth helpers and refactor publisher callers behind compatibility-preserving commands.
3. Add unit tests using temporary repositories and mocked GitHub command results, plus template render/update coverage.
4. Update generated rules/QA guidance and release an immutable platform version after validation and OpenSpec lifecycle completion.
5. Roll the release out as reviewable Copier updates. Existing projects get the state helper on update; no historical branch is sealed retroactively. Deleting a local state directory disables resume only until a new status/reseal operation rebuilds it.
