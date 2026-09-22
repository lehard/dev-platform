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

Keep these intents distinct:

- **Discuss** a change: inspect, design and compare options; a substantial discussion does not by itself create Backlog state.
- **Fix/add to Backlog** when the user explicitly asks to record accepted non-trivial work ("зафиксируй", "добавь в бэклог", "создай задачу", "отправь в бэклог" or equivalent): create or reuse a human-facing Business Requirement through `python3 scripts/requirement_intake.py create ...` and stop. Fixation creates no OpenSpec package and performs no technical decomposition or implementation.
- **Quick execution**: a small direct request remains a quick task and uses the existing task/check/finish workflow with no Requirement, backlog issue, or ceremonial OpenSpec. If it becomes material, stop and enter requirement-first or explicit technical managed intake before broadening scope.
- **Fresh non-trivial execution**: by default create/reuse a Business Requirement, run `requirement_intake.py start`, drive `orchestrate_pre_authoring.py` through evidence -> ADD -> intents -> handoff, author the resulting internal managed OpenSpec change(s), link each with `requirement_intake.py link-child`, start those managed tasks, and only then implement.
- **Execute an existing Business Requirement**: an explicitly supplied `type:requirement` Issue enters through `python3 scripts/requirement_intake.py start --requirement owner/repo#N`.
- **Direct technical managed/OpenSpec path**: when the user explicitly supplies an existing managed Issue/OpenSpec task or explicitly asks to create a technical managed task, preserve the existing `managed_task.py create` / `execute_managed_task.py` / `start_managed_task.py` path. This is not the default meaning of "зафиксируй".

Each internal technical child is linked back to its parent Requirement and labeled `type:internal-change`. Requirement progress is derived from child lifecycle state through `requirement_intake.py aggregate`; do not maintain a second manual status ledger. The primary human-facing Project view should show Requirements and exclude internal changes.

After a technical child is imported, `openspec/changes/<change>/` is canonical for that child's implementation, verification and archive. The parent Requirement remains the human-facing business/progress object, not a competing technical task list.

Goal refinement is a selective layer before authoring, used only for explicit goal-backed work or a materially unclear non-trivial request. It creates no durable goal, backlog or plan artifact. See [docs/engineering/agent-workflow.md](docs/engineering/agent-workflow.md).

## Always-on invariants

- **No silent divergence.** If implementation changes intent, behavior, design, or execution dependencies, update the corresponding proposal/spec/design/tasks artifact *first*. Do not knowingly let code drift from the active contract.
- **Verification is not a checkbox count.** A platform change is complete only after relevant tests, semantic OpenSpec verification, a truthful `verification.md` receipt, archive through the lifecycle helper, committed spec/archive changes, and publication — in that order. Completed-but-active changes are lifecycle debt and are blocked by platform CI.
- **Never fabricate a verification receipt.** The report must state what was actually checked and which method was used.
- **Managed contract conflicts stop.** Repair formal/schema mismatches in an imported package; a material product-contract conflict returns to the user.
- **Quick tasks do not silently grow.** If one expands into a material behavior, architecture, compatibility, data-contract or scope change, stop and enter requirement-first intake by default; use direct managed fixation only for explicit technical intent.
- **Routing is a required gate.** Every managed task carries a provider-neutral recommended start tier (`R2` balanced by default, `R3` frontier only with a recorded hard trigger) authored with the task. Execution still records a bounded routing decision through `scripts/dogfood_task.py route-codex` or `route-claude` before implementation, but that decision confirms the authored tier or escalates on newly discovered evidence rather than requiring a strong parent to redo full semantic routing from scratch. The user does not choose an executor, and a delegation is claimed only when its write containment is actually proven.
- **Other agents' state is off limits.** No containment, delegation or cleanup path stashes, resets, cleans or deletes integration state, and no task takes over another agent's worktree or scope without resolving the overlap.
- **Release refs are immutable.** Downstream reusable CI must never reference `dev-platform@main`; published release refs are append-only and must never be moved.
- **Keep CI providers thin.** Put portable test, build, verification, release, and deploy behavior behind repository-owned executable entrypoints; use provider workflows for their native orchestration. See [release-policy.md](docs/release-policy.md).
- **Resolve the friction checkpoint** before reporting a non-trivial task complete: `python3 scripts/agent_friction.py checkpoint --result none`, or the id of a recorded event.
- **Report blockers.** If a required completion step is blocked, say so instead of reporting the task as done.
- **Don't busy-poll background processes.** Wait out a long-running background command with one long timeout — for Codex, a single `write_stdin` call with `yield_time_ms` up to the runtime's max (around 300000) — instead of repeated short `sleep`/`ps` checks or empty stdin polls; poll again only once that wait elapses. Genuine interactive input is unaffected.

## Entrypoints

Ordinary work in this repository uses the committed source contract in `.dev-platform.toml` and its lifecycle adapter. Do not assemble a manual branch/worktree/PR flow.

```bash
python3 scripts/requirement_intake.py start --requirement owner/repo#N
python3 scripts/orchestrate_pre_authoring.py status --id requirement-N
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
| Optional engineering capability lifecycle and the browser verification adapter | [docs/engineering/engineering-capabilities.md](docs/engineering/engineering-capabilities.md), [docs/engineering/browser-verification.md](docs/engineering/browser-verification.md) |
| Provider-local executor selection, escalation, delegated write containment | [docs/engineering/model-routing.md](docs/engineering/model-routing.md) |
| Product/domain semantics, architecture invariants, anti-patterns or representative examples | [docs/context/README.md](docs/context/README.md) when that concern is reached |
| Release identity, downstream CI ownership, rollout registry, upgrade safety | [docs/release-policy.md](docs/release-policy.md) |
| Rollout registry ownership, GitHub App credentials, recovery | [docs/managed-rollout.md](docs/managed-rollout.md) |
| Platform-owned versus project-owned boundaries | [docs/ownership.md](docs/ownership.md) |

## Ownership

Promote a rule/tool only when it is reusable across projects or a defined workflow profile. Keep application-domain rules, credentials, machine-local paths and one-off workarounds in the owning project, and keep subtree-specific rules in a module-level `AGENTS.md` next to the code they govern.

`docs/context/` is a project-owned, selectively loaded context surface; it does not make every context document always-on guidance.

A change to a downstream managed file must consider both new-project rendering and Copier update behavior for existing projects. The shared lifecycle is composable: `light`, `standard`, and `multi-agent` profiles select capabilities rather than forking the template.

OpenSpec is external; do not vendor generated Claude/Codex skills.

## Optional engineering capabilities

Optional engineering capabilities are independent of `workflow_profile`. Use `python3 scripts/capability_manager.py list` to discover them and the same entrypoint for `create`, `enable`, `update`, `remove`, `audit`, and `sync`. `dev-platform/capabilities.toml` is the project opt-in; descriptors under `dev-platform/capabilities/` are canonical. Generated `.claude/.codex` skill surfaces are derived and must not be edited. OpenSpec-generated skills remain external to this lifecycle. The opt-in `browser-verification` capability adds bounded exploratory browser checks for web projects; see [docs/engineering/browser-verification.md](docs/engineering/browser-verification.md).
