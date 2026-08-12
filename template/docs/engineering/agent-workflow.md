# Agent workflow

The platform exposes one lifecycle with profile-specific capabilities:

`doctor -> sync origin -> start -> OpenSpec/implementation -> checks -> fetch origin again -> publish -> verify/archive`

## Profiles

- `light`: single-agent, synchronized integration branch, no mandatory feature branch/worktree/board.
- `standard`: feature branches + GitHub PR/direct publication; no mandatory worktrees/board.
- `multi-agent`: feature branches inside isolated worktrees + machine-local agent board and scope ownership.

Profiles select capabilities; they are not separate forks of the platform.

## Task intake

`AGENTS.md` owns the cross-agent task protocol. For an explicitly accepted non-trivial change that the user asks to record in Backlog, prepare a contained authoring bundle and run:

~~~
python3 scripts/managed_task.py create --bundle <directory>
~~~

The helper validates the configured `development_backlog` contract, target origin and temporary OpenSpec artifacts, then publishes exactly one package and stops. A bounded same-project/target candidate result requires the agent to decide scope explicitly before rerunning with `--confirm-distinct`; authoring never begins implementation.

Use the managed execution path only when the user explicitly supplies a Development Backlog task:

~~~
python3 scripts/start_managed_task.py owner/repo#N
~~~

The managed-start entrypoint reads one versioned package through existing GitHub authentication and validates the target checkout without writing. It then starts the normal task branch/worktree, materializes planning artifacts there, performs structural validation, and reconciles the matching Development Backlog Project item to `In progress`. It stops before OpenSpec apply, implementation, publication, or automatic dispatch. If Project identity, item mapping, expected Status options, or Projects mutation permission is unavailable, start fails explicitly and cleans up only the newly-created task workspace. The standalone importer remains for recovery inside a task checkout and for the `light` profile; it rejects direct materialization from platform-owned `standard` and `multi-agent` integration branches.

If Prepared against differs from the fetched integration commit, semantic preflight against current specs and active changes is mandatory. Formal/schema reconciliation is allowed; a material product-contract conflict must return to the user. After import, repository-local OpenSpec is the implementation contract and the backlog issue is provenance only.

Small direct requests remain quick tasks: use the normal start/check/finish lifecycle without creating a central issue. Escalate rather than silently expanding a quick task into a material behavior, architecture, compatibility, data-contract, or scope change.

Managed delivery projects lifecycle evidence onto the central board: an exact
reviewable PR becomes `In review`, while `Done` is written only after confirmed
delivery and local reconciliation. Normal CI/merge waiting stays `In review`.
For a real human/external stop, run
`python3 scripts/managed_project_status.py block --reason "..."`; after the
blocker clears, `resume` derives `In progress` versus `In review` from exact PR
evidence. `status --json` is read-only. The resolver uses configured
`development_backlog.project_owner` plus `project_number`, requires an
unambiguous Issue item and the six expected Status options, and needs GitHub
Projects authorization (`gh auth refresh -s project`). Quick tasks have no
managed provenance and therefore do not touch the Project.

Bootstrap exception: Development Backlog issue lehard/development-backlog#1 introduced the importer, so its package was manually scaffolded through the current OpenSpec CLI after target and semantic preflight. All later managed tasks use the managed-start command.

## Publishing

Protected main and zero-hand-off are compatible. The safe normal configuration for feature-capable projects is:

```toml
protected_main = true
publish_mode = "pr"
pr_merge_mode = "auto"
```

With that configuration, `finish_task.py` is a GitHub-backed reconciler, not a one-shot pipeline: every invocation re-observes the local task branch/head SHA, the configured base, any exact-matching PR (identified by repository/base branch + head branch + exact `headRefOid`, never by title/body text or a remembered PR number), required-check state, remote merge/auto-merge state, and whether local reconciliation remains, then performs only the next safe step. Required status checks remain authoritative; the platform never uses branch-protection bypass.

An already-open exact-head PR is detected and resumed *before* the first-publication fresh-base precondition. If `origin/main` has advanced since that PR was opened, the platform does not force a rebase just to satisfy a local check -- it re-observes GitHub and lets required checks/branch protection/auto-merge/merge queue decide whether the exact validated head can still integrate. A brand-new, never-published branch that is stale relative to `origin/main` is still rejected until it is explicitly rebased/updated and revalidated; only *existing* PR recovery skips that precondition.

For `pr_merge_mode=auto`, after a PR is created or reused, the platform prefers to arm GitHub's native auto-merge/merge-queue processing for the exact validated head *before* entering any long local wait (`gh pr merge --auto --match-head-commit <SHA>` or equivalent). Once GitHub accepts that request it persists independently of this process, so losing the caller after arming does not cancel it -- a later `finish_task`/`finish_task --status` invocation re-observes the same PR and continues from current remote state. Every ordinary/auto/queue merge request is guarded with the exact validated head SHA; if GitHub reports a different head before a request is accepted, the request fails closed and the changed head must be revalidated separately. If native auto-merge/queue is unavailable or disabled for the repository, the platform falls back to the existing bounded foreground required-check wait plus protected merge, and reports that path as degraded remote durability rather than pretending it is equally durable.

PR merge completion and required checks are determined from structured GitHub state for the current PR head, never from human-readable `gh` messages. Check registration, pending checks, and merge-queue confirmation each have bounded waits: a timeout leaves the PR and feature branch intact, does not change local `main`, and is safe to resume by rerunning the same `finish_task` command.

After GitHub confirms `MERGED`, and only then, multi-agent local reconciliation takes the shared integration lock. It re-fetches `origin/main` under that lock, fast-forwards or accepts an already-equal local `main`, reconciles the board, and optionally removes only its own completed worktree/branch. Remote CI and merge-queue waits never hold this lock, so independently finishing tasks can wait in parallel without Git/index races. The platform does not hold a long-lived publisher lease across those remote waits: repeated/concurrent publish attempts for the same exact head converge through PR re-observation, create-race re-query, and exact-head merge guards instead.

Run `python3 scripts/finish_task.py --status` for a strictly read-only view of the current task's publication state (not published / PR open-checks-pending / remote auto-merge armed-or-queued / blocked-failed-checks / remotely merged with local reconciliation pending / complete / GitHub state unavailable), including the exact task SHA and PR number/URL when known. `--status` never pushes, creates/merges a PR, arms a merge, mutates the board, removes a worktree, or changes local `main`; it does not even fetch in a way that would mutate local refs. Add `--json` for a sanitized machine-readable payload (no credentials, no raw logs). Normal `finish_task` is the resume/reconcile operation -- rerunning it after any interruption is always the correct next step; there is no separate `--resume` mode.

`pr_merge_mode=manual` keeps an explicit review stop after PR creation. Cross-repository Dev Platform rollout PRs remain reviewed and are not auto-merged by this task-publication policy.

Native auto-merge/merge-queue capability is a repository setting (`gh repo edit --enable-auto-merge`, or Settings > General > "Allow auto-merge"). The platform detects and reports that capability (`agent_doctor.py`, `finish_task.py --status`) but never enables or disables it automatically; enabling it is an explicit administrative/adoption action, and doing so does not by itself merge anything -- only a specific PR that the publication lifecycle explicitly arms becomes eligible.

`publish_mode=direct` is only valid for an intentionally unprotected integration branch. It re-fetches immediately before push and only pushes when remote main is an ancestor of local main. `protected_main=true` plus `publish_mode=direct` is an invalid configuration and doctor/finish preflight must reject it before local integration.

Platform-owned PR publication requires authenticated GitHub CLI/API access. Run `gh auth login` once on the agent host (or provide a supported `GH_TOKEN`/`GITHUB_TOKEN`). Doctor checks this before a protected-main task reaches publication. Git branch push and PR API operations are kept separate so validated work is not lost if `project_publish.py` is invoked directly in a partially configured environment.

## Local-heavy, cloud-final verification

`select_checks.py` has two deliberate policies: the default `local-affected` mode provides fast feedback only when every changed path has a maintained mapping; unknown paths and control-plane paths fail closed to the configured full set. `--mode protected-full` always runs that full set and is the only selector mode used by the reusable protected-PR gate. Successful commands print compact machine-readable duration/outcome evidence; failures also retain a bounded output tail. A local success is never merge authority.

For `harness_mode=platform`, its machine-readable selection state distinguishes `not-applicable`, `ready`, and `invalid-coverage`. An affected configured group with no commands, malformed evidence metadata, or a missing required evidence type is `invalid-coverage` and blocks validation. `checks.toml` may label command evidence with `evidence_types` and require a type (such as `test`) with `required_evidence_types`; syntax/compilation must not be labelled as product-test evidence. `harness_mode=project` retains ownership of its repository CI and is not made to implement this selector contract.

Required selected and full checks run locally before publication. The self-contained cloud workflow is the final clean-environment merge gate for `publish_mode=pr`. Protected PR publication waits for that gate before merging. Superseded validation runs for the same PR/ref are cancelled. Manual workflow dispatch remains the explicit cloud path for a full platform-managed run when that is useful.

For intentionally unprotected `publish_mode=direct` repositories, the published main state receives an automatic run that is deliberately lightweight: it validates platform/OpenSpec health without repeating the full project check set. Direct-mode repositories also retain the stable pull-request `platform-ci` gate for explicitly reviewed maintenance or rollout PRs so existing required-status protection can be satisfied if such a PR is used.

Do not skip local verification because cloud CI is narrower, and do not use the compatibility PR gate as a reason to duplicate expensive full/browser suites without a reviewed repository-specific need.

## Commands

```bash
python3 scripts/agent_doctor.py
python3 scripts/start_task.py my-task --task "OpenSpec add-x: 1-3" --scope "backend/..."
python3 scripts/select_checks.py --execute
python3 scripts/finish_task.py
python3 scripts/finish_task.py --status
```

The multi-agent profile may use `start_worktree.py` directly, but `start_task.py` is the preferred shared entrypoint.
