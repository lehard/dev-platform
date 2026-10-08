## Context

Verified current behavior in `template/scripts/model_routing.py`:

- `prepare` writes a `Route` with `pre_snapshot=_snapshot_to_dict(snapshot(integration))`. This snapshot covers the integration checkout only; it exists to prove a child did not escape into main (`postcheck`). Nothing records the state of the assigned task worktree, so a supervisor edit inside the task worktree is invisible until archive.
- `prepare_claude_handoff` returns `delegated: "pending_supervisor_invocation"` and the `claude_agent` spec, but there is no durable open-delegation record. `record_claude_execution` accepts any non-empty agent id at any time and writes `outcome: "claimed"`, so it can be called after the supervisor already wrote everything.
- `_retention_policy` allows supervisor retention only for `complex` (`complex-parent`) and for routine/standard on `STANDALONE_CLONE` (`parent-only-topology`). For routine/standard on a linked worktree `record_retained_execution` refuses ("proven child-writer path"). `record_retained_execution` is called after implementation, so even a permitted retained path is not declared before the work.
- `require_routing_gate` (archive/finish) is the only place the contradiction is detected: no execution -> "record a clean child execution or an explicit supported retained outcome". `scripts/dogfood_task.py:require_routing_gate` is called only from `finish`; `status` is routing-blind. `openspec_lifecycle.require_managed_routing_evidence` runs at archive, after tests.
- `escalate` can promote to `complex` with a free-text reason, after which `record_retained_execution` accepts supervisor-written work under `complex-parent`. This is the invented-escalation exit.

Defect: a required child executor can be silently replaced by supervisor-written implementation, discovered only late and then recoverable only by fabricating evidence.

## Goals

- One recorded, unambiguous execution plan before the first task-content mutation, truthful for both providers.
- Recommended tier (`start_tier`), plan (`execution_plan`) and actual executor (`execution`) are three distinct provenance facts.
- Contradiction surfaces at routing-adjacent commands before verification/archive.
- No recovery path creates delegation, launch evidence or an escalation trigger that did not happen.

## Decisions

1. **Plan is derived by policy, stored on the Route.** Add `execution_plan: dict | None` to `Route` (and `_route_from_payload`; absent in legacy records). `prepare` computes `mode = "supervisor-retained"` with `policy = _retention_policy(route)` when it is not None, else `mode = "delegated-child"`. Fields: `mode`, `policy` (retained only), `declared_at`, `task_content_pre`, `delegation` (null until opened). The caller supplies no mode; the existing rationale is the retained reason. The authored `start_tier` and the actual `execution`/`participant` remain separate fields, so a retained R3 or a delegated R2 is never conflated with the tier.

2. **Task-content pre-snapshot.** Use `delegation_containment.snapshot(task_root)` (content-aware porcelain fingerprints) on the assigned task worktree, preserve both source and destination changes across the full task tree (including deletions, moves and renames into excluded lifecycle locations), then drop allow-listed lifecycle paths: `openspec/changes/<change>/` (the materialized package, which tasks/verification legitimately edit), `.managed-task-state.json`, and the machine-local `.claude/` state. `task_content_pre` stores HEAD and the remaining path map. Route preparation refuses when the filtered state is non-empty, or when commits ahead of the merge base touch non-package paths (reusing the `task_content_identity` path helpers), with an error naming the diverged paths: routing must precede content. The comparison function `_task_content_diverged(route)` returns the changed paths relative to the pre-snapshot.

3. **Claude pre-launch delegation.** New `begin_claude_delegation(root)` / `model_routing.py begin-claude-delegation` / `dogfood_task.py begin-claude-delegation`: requires a Claude route with plan `delegated-child`, no execution, no open delegation, and task content equal to the pre-snapshot; writes `execution_plan.delegation = {"state": "open", "opened_at": ..., "provider": "claude", "launch_evidence": "self-reported"}`. `record_claude_execution` now requires an open delegation (no open delegation -> error naming the missing begin step and stating that after-the-fact recording is refused), keeps `launched: None` / `outcome: "claimed"`, and closes the delegation. `prepare_claude_handoff` output states `delegated: "pending_begin_delegation"` and names the two mandatory next steps. Still self-reported: nothing here claims platform-verified launch.

4. **Codex consistency.** `dispatch_codex` opens `delegation` with `launch_evidence: "platform-observed"` only after the child process has actually started. Every refusal or failure before launch (containment, runtime/login preflight or spawn error) immediately records a closed `not-launched` attempt. Such attempts never authorize supervisor-written content, retained finalization or escalation. A Codex route with plan `supervisor-retained` follows the same rules as Claude.

5. **Early gate.** `require_early_routing_gate(root)` (active change only, via `current_managed_identity`):
   - no route record and filtered task content non-empty -> fail ("route before task content");
   - plan absent (record predates this change) with no execution recorded -> fail with a named "re-route required" message (no silent legacy acceptance); records with a final execution outcome keep existing archive semantics;
   - plan `delegated-child`, no confirmed Codex launch or self-reported Claude delegation exists, and `_task_content_diverged` non-empty -> fail naming paths, the required `begin-claude-delegation`/`route-codex` step, and that supervisor-written content under a child-executor plan is blocked;
   - plan `supervisor-retained`, or a real delegated-child delegation open/closed: pass. Closed `not-launched` attempts and unlaunched execution receipts never qualify.
   Failure is `RoutingError`; callers exit non-zero. The check is read-only. It runs in `dogfood_task.py status` and `finish` (before `finish_task.py`), in the check/test execution entrypoint (`template/scripts/run_test_groups.py` main, before any group executes), in `model_routing.py verify-routing` for an active change, and stays in the archive gate. Projects without managed state or `model_routing` are unaffected, matching today's `has_state`/`has_active` guard.

5a. **Retained declared up front.** `record_retained_execution` requires `execution_plan.mode == "supervisor-retained"` with the same policy; it only finalizes (postcheck plus durable mirror). If the plan is `delegated-child` it refuses and does not convert the plan. There is no plan-switch command.

6. **Escalation and recovery stay truthful.** `escalate` may switch plan from `delegated-child` to `supervisor-retained` (`complex-parent`) only when a real delegation record exists (a child attempt happened and evidence was reviewed) or task content still equals the pre-snapshot. On a `delegated-child` plan with no delegation and diverged content it refuses: no invented trigger. `record_claude_execution` after the fact, `begin-claude-delegation` after content diverged, and plan changes after divergence are refused; there is no override flag. The refusal message states that a supervisor-written diff cannot be legalized and that the user must decide (discard the supervisor's own writes through an explicit user-owned action, or accept a recorded friction event). The platform never stashes, resets or cleans task state.

7. **No provider hook.** Enforcement is in repository-owned lifecycle entrypoints; a Claude editor hook cannot be shipped for all downstream runtimes and would be provider-specific.

8. **Recovery safety and retained finalization.** Re-routing and escalation must refuse unresolved containment violations and any Codex writer state other than released. A failed child may not become a new containment baseline until its original containment boundary passes (or an evidence-bound verified external-advance recovery exists). Retained finalization after escalation preserves the original child execution nested as `prior_execution`, together with the unchanged delegation and escalation provenance; it does not erase that outcome. These safety checks run again at finalization.

9. **Legacy claim normalization.** A plan-less legacy Claude execution with `launched: true`, an existing `agent_id` and no outcome may be re-recorded as a truthful claimed execution only with that same identifier and a fresh clean containment postcheck. This converts existing evidence; it creates no plan, retrospective delegation or launch claim. New planned routes still require an open delegation. Codex preflight refusal records a closed not-launched attempt and propagates the error, so it cannot authorize later supervisor writes or escalation.

10. **No fallbacks.** Missing or invalid plan/delegation fields raise `RoutingError` naming the field. No default plan is assumed when absent; no swallowed snapshot error (a failed snapshot is a gate failure, as `ContainmentError` already is).

## Risks

- Legacy active routes lack `execution_plan`; they fail the early gate until re-routed. Re-routing with already-diverged content is refused, which is the intended truthful outcome but needs a clear message (covered by a test).
- A failed or abnormal Codex child leaves partial content with `execution` recorded; the early gate passes it (execution is not None) and the existing archive gate keeps its current semantics. Supervisor decision (BR-415 ADD review): re-routing after partial content is permitted only when the current route carries a platform-observed delegation record (Codex `dispatch_codex`) whose recorded outcome is `failed` or `abnormal` and whose post-snapshot equals the current task content, so the divergence is provably attributable to that child; any other divergence is refused. A self-reported Claude delegation never qualifies. Regression tests cover both the permitted and the refused case.
- Allow-list drift: a new lifecycle path written by tooling into the task worktree would read as content. The allow-list is a single constant with a test enumerating managed-start artifacts.
- Existing tests call `record_claude_execution` straight after `prepare_claude_handoff`; they must add `begin_claude_delegation` first.

## Verification

Behavior-level tests with a real temporary integration plus linked task worktree (as in `ModelRoutingTests.setUp`): delegated R2 happy path (route, begin, child writes, record, gate passes at early and archive gates); complex and `parent-only-topology` supervisor-retained path declared at route time, work, `record_retained_execution`, gates pass; supervisor writes under a delegated plan without begin -> early gate fails in `status`, check entrypoint and `verify-routing`; record-after-the-fact refused; begin after divergence refused; route refused when content already diverged; escalate refused on diverged content without delegation and allowed with a real delegation; retained recording refused for a delegated plan; Codex dispatch records plan and platform-observed delegation; legacy record without plan handled explicitly. Run source and rendered template checks per the standard entrypoints and record actual commands and results in verification.md.

## Independent review repair clarification

Recovery checks the original containment boundary even when no execution receipt was saved. A permitted failed-child retry preserves the complete prior route (including executor identity, execution, plan and escalation history) in `rerouted_from`. The check/test entrypoint enforces the interactive early gate when local managed task state exists; a fresh source checkout containing only committed package metadata is not an executor and runs checks without resolving private local lineage.
