# Developer Platform Agent Rules

This repository is the central source of truth for reusable engineering process shared by multiple software projects. Treat changes here as potentially cross-project.

## Contract model

Do not treat platform sources as one flat hierarchy:

- `AGENTS.md` — process and safety constraints for changing the platform.
- `openspec/specs/` — accepted platform behavior after archived changes.
- `openspec/changes/<active>/` — approved deltas currently changing that behavior.
- `template/` and platform code — implementation of current specs plus active deltas.
- `docs/` — durable architecture, adoption and operating guidance.

Do not create a second backlog for work represented by an active OpenSpec change.

## No silent divergence

For non-trivial platform changes, use OpenSpec before implementation. If implementation changes intent, behavior, design, or execution dependencies, update the corresponding proposal/spec/design/tasks artifact first. Do not knowingly let code drift from the active contract.

## Managed and quick task intake

Keep four distinct intents: discuss (no Backlog state); explicitly fix/add an accepted non-trivial change to Backlog; quick execution; and execution of an existing managed task. For explicit fixation (“зафиксируй”, “добавь в бэклог”, “создай задачу” or equivalent), prepare a local authoring bundle and run `python3 scripts/managed_task.py create --bundle <directory>`. The bundle contains `manifest.json` (`title`, `change`, ordered `artifacts`), `issue.md`, and those artifacts. The helper validates the configured Backlog contract and temporary OpenSpec change, performs bounded duplicate checking, publishes one `managed-openspec:v1` package, then stops. Review potential-overlap candidates and pass `--confirm-distinct` only after deciding the scopes are separate. Do not implement, apply, dispatch, publish, or change Project state after authoring; wait for a separate execution request.

An explicitly supplied Development Backlog issue is a managed task. Run "python3 scripts/start_managed_task.py owner/repo#N" before implementation; it performs read-only package intake, creates the task branch/worktree, materializes the agreed package only in that task checkout, then reconciles the configured Development Backlog Project item to `In progress`. It does not start apply, dispatch, or publication. Missing Project configuration/permission is a resumable start blocker, not a silent stale `Ready` state. `managed_task.py` is a task-checkout-only importer for recovery and light-profile use; it must not materialize files in a feature-capable integration checkout. Then compare the materialized change with current specs and active changes. Repair formal/schema mismatches, but stop for user resolution if the product contract materially conflicts.

For managed tasks, publication reconciles an exact reviewable PR to `In review`, and terminal finish reconciles `Done` only after GitHub merge/direct delivery plus required local synchronization. Ordinary CI waiting remains `In review`. Use `python3 scripts/managed_project_status.py block --reason "..."` only for a genuine external/human stop, `resume` after it clears, and `status --json` for read-only recovery evidence. These commands require GitHub Projects read/write authorization (`gh auth refresh -s project`). Quick tasks without managed provenance do not mutate the Development Backlog Project.

After successful import, the local "openspec/changes/<change>/" artifacts are canonical for implementation, verification, and archive. The backlog issue remains the human-facing provenance item, not a competing implementation task list.

A small direct request is a quick task and may use the existing task/check/finish workflow without creating a backlog issue or ceremonial OpenSpec. If it expands into a material behavior, architecture, compatibility, data-contract, or scope change, stop and propose fixation as a managed task instead of broadening it silently.

Before archiving a non-trivial platform change, run relevant tests plus semantic OpenSpec verification. Prefer `/opsx:verify` when the installed tool integration exposes it. If the current agent environment cannot invoke that workflow, perform and document the equivalent OpenSpec review across completeness, correctness, and coherence. Structural `openspec validate` is useful but is not a substitute for semantic verification or project-specific checks.

A platform change is not done merely because its task checkboxes are complete. After semantic verification succeeds and material findings are resolved, record `OpenSpec-Verify: PASS` and `Verification-Method: <method>` in the active change's `verification.md`, archive through the platform lifecycle helper, commit the resulting current-spec/archive changes, and only then publish. Completed-but-active changes are treated as lifecycle debt and are blocked by platform CI.

For the central repository, the lifecycle helper is invoked as:

```bash
python3 template/scripts/openspec_lifecycle.py archive <change>
```

## Central source dogfood lifecycle

For ordinary work in this central repository, use the committed source contract
in `.dev-platform.toml` and its lifecycle adapter. Do not assemble a manual
branch/worktree/PR flow. A managed task is imported first, then its sole
untracked package is transferred into the isolated task worktree:

```bash
python3 scripts/managed_task.py owner/repo#N
python3 scripts/dogfood_task.py start <slug> --task "owner/repo#N" --scope "paths" --change <openspec-change>
cd .claude/worktrees/<slug>
python3 scripts/dogfood_task.py status
python3 scripts/dogfood_task.py finish
```

`status` is read-only. `finish` delegates to the authoritative GitHub-backed
publication/reconciliation lifecycle and is resumable; branch pushed, draft or
open PR, and green checks are nonterminal states. Do not report source work as
complete until GitHub reports the exact PR `MERGED` and local `main` has been
reconciled (with cleanup warnings classified under the shared lifecycle policy).

Do not fabricate a verification receipt. The verification report must state what was actually checked and which method was used.

## Scope discipline

Promote a rule/tool only when it is reusable across projects or a defined workflow profile. Keep application-domain rules, credentials, machine-local paths and one-off workarounds in the owning project.

A change to a downstream managed file must consider both new-project rendering and Copier update behavior for existing projects.

## Platform capabilities

The shared lifecycle is composable. `light`, `standard`, and `multi-agent` profiles select capabilities rather than forking the template. GitHub sync/publish, checks, OpenSpec policy and release pinning are core; worktrees/board are multi-agent capabilities.

## Delegated write containment

A write-capable delegated subagent/subprocess (Codex, Claude, or any other runtime with filesystem write access) is platform-contained only when it runs through the guarded entrypoint in `template/scripts/delegated_write_guard.py` (`run_guarded_delegation`). It validates an absolute, registered `assigned_worktree`, applies the strongest enforcement tier the runtime can actually prove (`hard` for a real OS writable-root sandbox whose known extra writable roots do not overlap protected repository paths, or a hook-enforced structured-write-only Claude session; `detection-only` otherwise), launches the child with `cwd=assigned_worktree`, and always runs a content-aware post-delegation comparison against the integration copy before reporting success — even when the child fails, times out, or is cancelled. For Codex, temp roots such as `/tmp` and `$TMPDIR` are compared using realpath semantics; unsafe topology downgrades to `detection-only`, or fails before launch when hard containment is required.

Direct native subagent/subprocess invocation outside that entrypoint is not represented as platform-contained, regardless of how it happens to behave. `detection-only` delegation must not start while the integration checkout already has uncommitted state, since a purely after-the-fact check cannot tell a pre-existing dirty path from writer-caused damage the way a hard-contained run's post-check still can. No containment path stashes, resets, cleans, or deletes anything in the integration copy; a detected violation is reported with the exact paths and recorded as local friction, independent of GitHub auth.

## Release safety

Downstream reusable CI must never reference `dev-platform@main`. It must use a versioned release ref (or immutable SHA). Release refs are append-only and must never be moved after publication. Platform upgrades reach projects through reviewed Copier update PRs.

`managed-projects.json` is the explicit project inventory and cross-repository rollout allowlist. Automation must write only to entries whose state is `managed`. `candidate` means reviewed adoption is still expected; `excluded` records an intentional non-adoption decision. Both are non-mutating states. Do not silently omit a known project to avoid classifying it.

Exact-version rollout must target an immutable published SemVer release, fail closed on conflicts/ownership ambiguity, never force-push, and never auto-merge by default.

Cross-repository rollout credentials must come from the dedicated least-privilege GitHub App. Use separately down-scoped source-read and target-write tokens; target rollout needs Contents, Pull requests and Workflows write because platform updates can change `.github/workflows/*`. Never commit the App private key, installation token or a fallback personal access token.

## Validation

At minimum:

```bash
python3 -m compileall -q template/scripts scripts
python3 scripts/managed_projects.py validate
python3 -m unittest discover -s tests -v
python3 template/scripts/openspec_lifecycle.py check
```

When Copier is available, render the template and compile/run the generated doctor. For Git lifecycle changes, exercise temporary local/bare remotes so fetch/sync/direct-publish safety is tested.

## OpenSpec dependency policy

OpenSpec is external; do not vendor generated Claude/Codex skills. `.dev-platform.toml` records minimum/tested CLI versions. The doctor may warn/fail on version compatibility but must not silently mutate a user's global OpenSpec installation.

## Friction routing

Raw friction evidence stays machine-local. Record high-signal events through `scripts/agent_friction.py`; the normal path automatically upserts a bounded sanitized, fingerprinted process issue in the configured project or platform repository. Retry failure is durable and non-blocking for safe delivery. Process issues are evidence only: cloud triage/review must never create managed tasks, OpenSpec, implementation PRs, or code changes. Before non-trivial completion, resolve the friction checkpoint with `python3 scripts/agent_friction.py checkpoint --result none` or a recorded event id.
