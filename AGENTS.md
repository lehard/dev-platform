# Developer Platform Agent Rules

This repository is the central source of truth for reusable engineering process shared by multiple software projects. Treat changes here as potentially cross-project.

This file is the canonical repository-wide map of that process: sources of truth, task intents, always-on invariants, entrypoints and where the detailed contract lives. It is deliberately bounded. Detailed workflow rules live in the linked documents and are read when a task reaches that concern. `CLAUDE.md` and any other tool-specific file only reference this contract; they never fork or duplicate it.

## Sources of truth

Do not treat platform sources as one flat hierarchy:

- `AGENTS.md` and any applicable module-level `AGENTS.md` — process and safety constraints for changing the platform.
- `openspec/specs/` — accepted platform behavior after archived changes.
- `openspec/changes/<active>/` — approved deltas currently changing that behavior.
- `template/` and platform code — implementation of current specs plus active deltas.
- `docs/` — durable architecture, adoption and operating guidance.

Target behavior during an active change is `current specs + active delta`, subject to process/safety constraints. A safety/process rule is not silently bypassed because an OpenSpec artifact conflicts with it — report the conflict. Do not create a second backlog for work represented by an active OpenSpec change.

## Task intents

Keep these four intents distinct:

- **Discuss** a change: inspect, design and compare options; a substantial discussion does not by itself create Backlog state.
- **Fix/add to Backlog** from a repository checkout when the user explicitly asks to record an accepted non-trivial change ("зафиксируй", "добавь в бэклог", "создай задачу" or equivalent): prepare a local authoring bundle, run `python3 scripts/managed_task.py create --bundle <directory>`, and stop. Authoring never starts apply, implementation, dispatch, Project-status changes or delivery publication. ChatGPT Project uses its dedicated adapter for the same semantics when it has no checkout.
- **Quick execution**: a small direct request is a quick task and uses the existing task/check/finish workflow with no backlog issue and no ceremonial OpenSpec. If it becomes material or needs a full active OpenSpec contract, enter managed intake before further implementation.
- **Fresh non-trivial execution**: explicit execution intent first creates/reuses the managed task and starts that same task before implementation; use `python3 scripts/execute_managed_task.py --bundle <directory>`.
- **Execute an existing managed task**: an explicitly supplied Development Backlog issue is imported with `python3 scripts/start_managed_task.py owner/repo#N` before implementation.

Managed start performs read-only package intake, creates the task branch/worktree, materializes the agreed package only in that task checkout, and reconciles the Development Backlog Project item to `In progress`. After import, `openspec/changes/<change>/` is canonical for implementation, verification and archive; the backlog issue remains the human-facing provenance item, not a competing implementation task list.

Goal refinement is a selective layer before authoring, used only for explicit goal-backed work or a materially unclear non-trivial request. It creates no durable goal, backlog or plan artifact. See [docs/engineering/agent-workflow.md](docs/engineering/agent-workflow.md).

## Always-on invariants

- **No silent divergence.** If implementation changes intent, behavior, design, or execution dependencies, update the corresponding proposal/spec/design/tasks artifact *first*. Do not knowingly let code drift from the active contract.
- **Verification is not a checkbox count.** A platform change is complete only after relevant tests, semantic OpenSpec verification, a truthful `verification.md` receipt, archive through the lifecycle helper, committed spec/archive changes, and publication — in that order. Completed-but-active changes are lifecycle debt and are blocked by platform CI.
- **Never fabricate a verification receipt.** The report must state what was actually checked and which method was used.
- **Managed contract conflicts stop.** Repair formal/schema mismatches in an imported package; a material product-contract conflict returns to the user.
- **Quick tasks do not silently grow.** If one expands into a material behavior, architecture, compatibility, data-contract or scope change, stop and propose fixation as a managed task.
- **Routing is a required gate.** Every managed task carries a provider-neutral recommended start tier (`R2` balanced by default, `R3` frontier only with a recorded hard trigger) authored with the task. Execution still records a bounded routing decision through `scripts/dogfood_task.py route-codex` or `route-claude` before implementation, but that decision confirms the authored tier or escalates on newly discovered evidence rather than requiring a strong parent to redo full semantic routing from scratch. The user does not choose an executor, and a delegation is claimed only when its write containment is actually proven.
- **Other agents' state is off limits.** No containment, delegation or cleanup path stashes, resets, cleans or deletes integration state, and no task takes over another agent's worktree or scope without resolving the overlap.
- **Release refs are immutable.** Downstream reusable CI must never reference `dev-platform@main`; published release refs are append-only and must never be moved.
- **Resolve the friction checkpoint** before reporting a non-trivial task complete: `python3 scripts/agent_friction.py checkpoint --result none`, or the id of a recorded event.
- **Report blockers.** If a required completion step is blocked, say so instead of reporting the task as done.

## Entrypoints

Ordinary work in this repository uses the committed source contract in `.dev-platform.toml` and its lifecycle adapter. Do not assemble a manual branch/worktree/PR flow.

```bash
python3 scripts/start_managed_task.py owner/repo#N
python3 scripts/execute_managed_task.py --bundle <directory>
python3 scripts/dogfood_task.py route-claude --profile <routine|standard|complex> --rationale "..." --evidence "..."
python3 scripts/dogfood_task.py status
python3 scripts/dogfood_task.py reconcile
python3 template/scripts/openspec_lifecycle.py archive <change>
python3 scripts/dogfood_task.py finish
```

`status` is read-only and reports task freshness before expensive validation. If it requires reconciliation, run `python3 scripts/dogfood_task.py reconcile`; it refuses dirty or ambiguous state, merges current main without history rewrite, and a published exact PR is fast-forward pushed on the same branch. Rerun validation before `finish`, which delegates to the authoritative GitHub-backed publication lifecycle and is resumable. Do not report source work as complete until GitHub reports the exact PR `MERGED` and local `main` has been reconciled.

Minimum validation before finishing:

```bash
python3 -m compileall -q template/scripts scripts
python3 scripts/managed_projects.py validate
python3 scripts/run_test_groups.py --all
python3 template/scripts/openspec_lifecycle.py check
```

## Where the detailed contract lives

| Concern | Canonical document |
| --- | --- |
| Maintaining agent-facing instructions, pointers and surface ownership | [docs/engineering/agent-instructions.md](docs/engineering/agent-instructions.md) |
| Task intake and intent transitions | [docs/engineering/task-intake.md](docs/engineering/task-intake.md) |
| ChatGPT Project authoring through connected GitHub | [docs/engineering/chatgpt-project-protocol.md](docs/engineering/chatgpt-project-protocol.md) |
| Goal refinement, dogfood lifecycle, scope discipline, validation, friction, completion | [docs/engineering/agent-workflow.md](docs/engineering/agent-workflow.md) |
| OpenSpec contract model, semantic verification, receipts, archive, dependency policy | [docs/engineering/openspec-workflow.md](docs/engineering/openspec-workflow.md) |
| Provider-local executor selection, escalation, delegated write containment | [docs/engineering/model-routing.md](docs/engineering/model-routing.md) |
| Release identity, downstream CI ownership, rollout registry, upgrade safety | [docs/release-policy.md](docs/release-policy.md) |
| Rollout registry ownership, GitHub App credentials, recovery | [docs/managed-rollout.md](docs/managed-rollout.md) |
| Platform-owned versus project-owned boundaries | [docs/ownership.md](docs/ownership.md) |

## Ownership

Promote a rule/tool only when it is reusable across projects or a defined workflow profile. Keep application-domain rules, credentials, machine-local paths and one-off workarounds in the owning project, and keep subtree-specific rules in a module-level `AGENTS.md` next to the code they govern.

A change to a downstream managed file must consider both new-project rendering and Copier update behavior for existing projects. The shared lifecycle is composable: `light`, `standard`, and `multi-agent` profiles select capabilities rather than forking the template.

OpenSpec is external; do not vendor generated Claude/Codex skills.
