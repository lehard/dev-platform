## Context

The original design assumed a broader set of missing lifecycle guarantees than the platform has today. Since then, the v1.4.20-v1.4.22 stabilization chain shipped independent GitHub credential fallback, structured required-check observation, protected merge/auto-merge/queue negotiation, authoritative remote `MERGED` handling, serialized local post-merge reconciliation, and exact-head recovery after a PR was already merged.

Today `finish_task.py` still drives automatic PR publication in one foreground invocation. `project_publish.py` pushes the branch, creates/reuses the PR, waits for required checks, asks GitHub to merge, and only then returns for local reconciliation. The operations are already partly idempotent, but there is no explicit read-only publication status and the code does not arm GitHub's native durable merge processing before the foreground wait. The current merge commands also do not consistently guard every merge request with the exact validated head SHA.

GitHub itself already stores the durable remote objects we care about: branch ref/head SHA, PR identity/head OID, required checks, auto-merge request, merge queue state, and terminal merge state. Duplicating those phases into a machine-local journal would create another state system that can be deleted, corrupted or drift from GitHub.

## Goals / Non-Goals

**Goals:**

- Make automatic PR publication restartable from authoritative Git + GitHub observation rather than event history.
- Persist the remote waiting step in GitHub itself whenever native auto-merge / merge queue is supported.
- Ensure every merge request is tied to the exact validated task head.
- Give agents and doctor one concise read-only status model for unfinished delivery.
- Preserve current zero-hand-off behavior when the foreground process stays alive, while making caller loss harmless after GitHub accepts remote merge orchestration.
- Keep implementation dependency-light and compatible with current platform-managed profiles.

**Non-Goals:**

- Add a daemon, Temporal-like workflow service, database, or mandatory local publication-state journal.
- Reimplement already-shipped GitHub authentication fallback.
- Automatically change repository settings from `finish_task` or publication code.
- Auto-publish dirty, uncommitted, unvalidated, changed-head, or manually reviewed work.
- Replace project-owned publication harnesses.
- Solve unrelated browser/Playwright discovery in this change.

## Decisions

### Use a level-based reconciler, not a local event journal

Publication SHALL be modelled as reconciliation from observed state. Each invocation reads the local branch/head, remote branch, matching PR metadata, required checks, remote merge orchestration state, and local integration state; it then performs only the next safe idempotent transition and re-observes.

This follows the controller/reconciliation pattern used by Kubernetes controllers: compare desired state with actual state, operate on the actual state, and make repeated reconciliations converge instead of depending on receiving every prior event.

The desired state for `harness_mode=platform`, `publish_mode=pr`, `pr_merge_mode=auto` is: the exact validated task head is represented by one PR, GitHub is instructed to merge it through normal protection, the PR reaches `MERGED`, and local integration/board/worktree reconciliation completes.

A machine-local publication journal is rejected for v1 because Git/GitHub already provide stable identity for all remote boundaries. A local cache MAY be added later for performance or diagnostics only if real evidence shows authoritative observation is insufficient; it SHALL NOT become the source of truth for publication safety.

### Identify a candidate from current facts, not a remembered phase

The safe candidate identity is the configured repository/base branch plus task branch and exact head SHA observed after local validation. Existing PR discovery must verify base branch and `headRefOid` instead of trusting a title, stale PR number, or branch name alone.

Normal `finish_task` remains responsible for clean-worktree, OpenSpec lifecycle and selected-check validation. If the branch head changes, the next invocation treats it as a new candidate and revalidates it; no previous observation authorizes the changed head.

An open PR for the exact task head is a resumable remote object. It SHALL be detected before the existing stale-base rejection that applies to first publication. The platform may resume that existing exact-head PR even if base advanced after the PR was opened, because GitHub required checks / branch protection / merge queue remain the integration authority. If repository policy requires an up-to-date branch and no supported queue/auto path can satisfy it, the lifecycle reports that concrete blocker rather than rewriting the candidate silently.

### Arm GitHub's native durable merge processing before waiting

After creating or reusing an exact-head PR in automatic mode, the publisher SHALL prefer to request native GitHub auto-merge / merge-queue processing immediately, before entering a long foreground check wait.

Use the GitHub CLI/API exact-head guard (`gh pr merge --match-head-commit <SHA>` or equivalent expected-head API semantics) on every ordinary, auto-merge, or queue merge request. If GitHub accepts auto-merge/queue enrollment, that remote request survives caller output loss and GitHub continues processing required checks independently.

The normal caller may still wait for `MERGED` so it can finish local reconciliation in one invocation. If the process disappears, a later status/finish invocation re-observes the same PR and continues from current remote state without needing a local phase cursor.

If native auto-merge is disabled or otherwise unsupported, keep the current bounded foreground required-check wait and protected merge fallback. That fallback remains restartable through exact-head PR observation, but the status model SHALL report that remote durability is degraded until a later invocation runs.

### Prefer native GitHub capability over rebuilding a workflow engine

GitHub auto-merge already merges only after required reviews/status checks are satisfied, and merge queues provide durable protected-branch integration without requiring the author to keep rebasing while the queue is active. The platform should use those primitives rather than reproduce them in a local state machine.

For `pr_merge_mode=auto`, doctor/status MAY query repository capability (for example REST `allow_auto_merge`) and report one of:

- `remote_armed_capable`: native remote auto-merge/queue can persist the waiting step;
- `foreground_fallback`: publication remains safe and resumable but requires a live/restarted publisher to request the final merge;
- `manual`: repository/task policy intentionally requires human review.

The publication path SHALL NOT silently enable repository auto-merge. Enabling that repository capability is an explicit administrative/adoption action and does not itself auto-merge any PR until a specific PR is armed.

### Idempotency replaces an end-to-end publisher lease

Do not hold a long lease across GitHub waits. Remote operations must be convergent instead:

- pushing the same exact branch/head is idempotent;
- PR creation first re-observes an exact matching PR; if a concurrent creator wins the race, the loser re-queries and reuses it;
- merge requests include the exact expected head SHA;
- repeated auto-merge/queue requests either confirm already-armed state or remain harmless;
- remote `MERGED` remains authoritative;
- local integration mutation remains protected by the already-existing integration lock.

A short local mutation lock MAY be used if implementation demonstrates a concrete same-host race that GitHub idempotency cannot absorb, but the design does not introduce PID/expiry lease semantics without evidence that they are necessary.

### Status is a read-only observation

Add `finish_task --status` (or an equivalently simple exact CLI surface confirmed during implementation). It SHALL not push, create a PR, arm merge, mutate the board, or touch local main.

For the current task branch it reports sanitized structured fields such as candidate SHA, PR number/URL if any, PR state, required-check bucket, whether native remote merge is armed/capable, and whether remote merge or local reconciliation remains. It never reports credentials or raw arbitrary logs.

Normal `finish_task` is the resume operation; a separate `--resume` mode is not required unless implementation evidence shows it materially reduces ambiguity. Re-running normal finish must revalidate local safety and then call the same reconciler.

### Keep authentication as baseline, not scope

The current `_platform_common.github_cli_env` already validates inherited token environment, a token-free persistent `gh` session, and a git credential-helper candidate independently. This change relies on that behavior and adds regression coverage only where the new reconciler touches it; it does not redesign credential selection again.

### Browser QA is explicitly split out

Browser executable/cache discovery has no publication-state dependency and broadens the blast radius into QA/runtime configuration. It is removed from this OpenSpec. If browser QA unavailability becomes a demonstrated recurring problem, it should receive a separate narrowly scoped change.

## External patterns deliberately borrowed

- **Kubernetes/controller-runtime reconciliation:** level-based reconciliation re-reads actual state on every invocation instead of replaying event history. That maps directly to Git/GitHub publication.
- **GitHub native auto-merge and merge queue:** GitHub is the durable remote executor for waiting on branch-protection requirements.
- **Exact expected-head compare-and-set semantics:** `gh pr merge --match-head-commit` / GitHub expected-head OID prevents a changed PR head from being merged under a stale validation decision.

Not adopted:

- **Temporal / durable workflow engines:** technically capable, but would add a service/runtime dependency far larger than this CLI publication problem warrants.
- **Terraform-style local state:** Terraform needs state to map configuration objects to remote objects that otherwise lack stable bindings. Here branch + PR + head OID already provide that mapping, so a second authoritative state file would add drift risk without equivalent benefit.

## Risks / Trade-offs

- [Repository auto-merge disabled] → Safe foreground fallback remains; doctor/status reports degraded remote durability and exact optional admin remediation.
- [Two publishers race] → Exact-head PR observation, re-query on create conflict, expected-head merge guards, and existing local integration lock make repeats convergent.
- [Base advances after PR creation] → Existing exact-head PR may continue through GitHub protection/queue; if repository policy cannot integrate it without updating the branch, stop with that actionable blocker rather than mutating the candidate silently.
- [Head changes after validation] → Expected-head merge request fails closed; next finish must revalidate the new SHA.
- [GitHub outage] → No local-main mutation; status becomes unknown/recoverable and a later finish re-observes.
- [Auto-merge is disabled by a later head/base change] → Status re-observes `autoMergeRequest`/head OID and does not assume the prior request is still active.

## Migration Plan

1. Refactor platform-owned PR publication around observe/reconcile helpers while preserving existing CLI behavior.
2. Add exact-head PR discovery, exact-head merge guards, early native auto-merge/queue arming, read-only status, and restart/concurrency tests.
3. Merge the implementation through protected main while live-acceptance tasks remain explicitly incomplete in the active OpenSpec.
4. Publish the next normal immutable platform release containing the implementation and roll it to the platform-owned managed consumers needed for live acceptance.
5. Run real acceptance after the released code is installed: one consumer with native auto-merge explicitly enabled to prove remote execution survives caller loss, and one disabled/unavailable case to prove the foreground fallback remains resumable.
6. Only after live acceptance passes, record semantic verification, archive the OpenSpec, rerun validation, and publish the archive/current-spec update. Do not cut a second release solely for archive/spec-only changes when runtime/template code did not change after the accepted release.
7. Project-owned harnesses remain untouched throughout.
