## Context

The change began with three gaps: no cloud review runtime, a manual friction-promotion path, and no structural completion trigger forcing an agent to decide whether meaningful friction occurred. The first two are now largely implemented and proven: pinned `gh-aw` workflows provide bounded cloud advisory review, and local high-signal friction can be routed as sanitized deduplicated GitHub process evidence with durable retry.

The first implementation of the completion guard also landed: a non-trivial platform-owned task must resolve a friction checkpoint as `none` or one recorded event reference. Real usage exposed that this guard is structurally present but semantically too weak. An agent can satisfy `none` without performing a separate retrospective analysis, while a later human prompt to inspect unresolved process problems still surfaces additional findings. The checkpoint therefore risks becoming exactly the ceremony the design intended to avoid.

`bind-terminal-reconciliation-to-managed-task-provenance` (`lehard/development-backlog#18`) is now completed, so task-local/exact managed-task identity is available as the safe basis for freshness-aware retrospective evidence. The refinement should reuse that lifecycle provenance rather than introduce another task identity system.

The remaining design goal is not a generalized self-improving agent framework. It is a small but explicit two-phase completion contract:

`post-task retrospective -> 0..N friction findings -> current completion receipt -> finish`

## Goals

- Make the agent perform a real bounded process review before non-trivial platform-owned terminal completion without requiring a human reminder.
- Make `none` mean “review completed with zero new meaningful unresolved/unrecorded findings,” not “nothing was entered.”
- Allow one retrospective to surface multiple independent findings.
- Avoid duplicate/noisy friction by filtering findings already resolved or already recorded.
- Bind retrospective completion evidence to current task execution identity strongly enough to reject stale reuse.
- Keep existing sanitized routing, dedupe, retry, and advisory cloud review unchanged where possible.
- Keep a deliberate human decision between process evidence and a managed implementation task.

## Non-goals

- Autonomous code fixes, OpenSpec acceptance, Development Backlog creation, or executor dispatch from process evidence.
- Transcript warehousing, a generic conversation-analysis database, MemoryOps, or a background daemon.
- Per-agent hooks as the authoritative correctness boundary.
- A second lifecycle state machine or task identity database.
- Heavy retrospective ceremony for ordinary tiny quick tasks outside the existing non-trivial platform-owned completion contract.
- Downstream `gh-aw` rollout in this change.

## Decisions

### 1. Preserve the working cloud pilot

`Process Issue Triage` and `Weekly Process Backlog Review` remain the cloud advisory layer. Their safe-output, public-data, runtime, and cost boundaries remain unchanged unless acceptance exposes a concrete defect.

Cloud agent success remains independent from deterministic CI/publication/release correctness.

### 2. Keep one normal friction path

The normal evidence path remains:

`structured local event -> sanitized candidate -> deterministic GitHub issue upsert -> gh-aw triage/review`

Raw evidence remains machine-local. Routing failure remains durable and non-blocking for otherwise safe delivery.

### 3. Process issues and managed tasks stay separate

A process issue is evidence/inbox state. A Development Backlog issue plus OpenSpec is an explicit human decision to manage a change. Retrospective, routing, triage, and weekly review SHALL NOT cross that boundary automatically.

### 4. Completion becomes explicitly two-phase

For non-trivial platform-owned work, the old bare checkpoint is no longer sufficient by itself.

Before terminal completion, the agent performs one bounded post-task semantic retrospective. Only after this pass may completion evidence be resolved.

The retrospective reviews meaningful execution signals, including:
- user corrections or changed understanding caused by an avoidable miss;
- repeated substantive failures or excessive retries;
- manual workaround or unsupported detour;
- safety near-miss;
- false premise;
- undocumented invariant;
- missing automation or documentation that materially slowed/repeated work;
- auth/tool/worktree/Git/OpenSpec/CI/lifecycle friction;
- avoidable repeated actions;
- problems noticed but intentionally left unresolved.

The retrospective is not expected to catalog routine successful work.

### 5. Classify before recording

Each retrospective candidate is classified as one of:
1. resolved in this task;
2. already recorded/represented;
3. new meaningful unresolved and unrecorded friction.

Only class 3 is newly recorded. This preserves signal quality while still allowing several distinct new findings from one task.

Existing issue/event dedupe remains a second safety layer after this semantic classification.

### 6. Retrospective result supports 0..N findings

The completion representation must support:
- zero new findings (`none`, but only after the review ran);
- one finding;
- multiple findings/events.

The current single-event checkpoint shape is therefore an implementation detail to evolve, not a product constraint.

A likely minimal shape is one task-local retrospective receipt containing a list of event ids plus review metadata. The exact CLI/storage schema is implementation-owned during preflight, provided it remains small, machine-checkable, and compatible with the existing friction state.

### 7. Freshness reuses task-local provenance

A retrospective receipt must not be silently reusable after substantive task execution changes.

Use the smallest existing identity already made reliable by managed-task provenance and publication lifecycle — for example task source/change plus branch/head or an equivalent exact execution marker. Do not invent another global task database.

For quick tasks that still use the non-trivial platform-owned completion contract but have no Development Backlog provenance, use the existing task/branch/head lifecycle identity available to `finish_task`.

### 8. `finish_task` remains authoritative

The authoritative completion boundary verifies:
- a retrospective result exists for work that requires it;
- the result is fresh for the current task execution state;
- referenced positive findings exist locally;
- routing failure alone does not invalidate otherwise safe completion.

Missing/stale evidence produces an actionable blocker asking the agent to run the retrospective. `finish_task` must never auto-create `none`.

### 9. Deterministic failures still record themselves

Machine-classifiable lifecycle/process failures should be recorded when observed, not delayed until retrospective time. The final retrospective treats those events as already-recorded evidence and avoids duplicates.

### 10. Cross-agent guidance owns the semantic pass

Generated `AGENTS.md` guidance for Codex/Claude must explicitly require the separate retrospective reasoning pass and candidate classification before resolving completion. The final response should include a compact retrospective result.

This guidance plus the deterministic receipt gate is the correctness model. Agent-specific shell hooks are not required as the primary boundary.

### 11. Weekly review remains advisory and bounded

The scheduled weekly workflow keeps summarizing open process issues for human decisions. The existing acceptance requirement for a genuine scheduled run remains.

### 12. Keep the central pilot boundary

This change completes the central `dev-platform` loop only. Consumer workflow rollout remains a separate managed decision.

## Updated execution shape

1. Preserve current routing/cloud behavior and validation.
2. Extend friction state/CLI with a compact post-task retrospective receipt that supports 0..N event references and current-task freshness.
3. Make `finish_task` require the fresh receipt.
4. Update cross-agent completion guidance to perform the semantic review and classification before writing the receipt.
5. Add regression tests for multi-finding, clean `none`, resolved/already-recorded filtering, stale evidence, and routing failure.
6. Observe the still-required genuine scheduled weekly review.
7. Run semantic verification, archive, and release only when all acceptance evidence is truthful.

## Risks and mitigations

- **Retrospective becomes another checkbox:** separate it from the old checkpoint semantically, require explicit review guidance, support multiple findings, and reject a stale/missing receipt.
- **Model still claims `none` too casually:** make the required reviewed signal classes explicit and require a dedicated pass in shared agent guidance; the platform cannot prove hidden reasoning without adding an unwanted transcript-analysis system.
- **Issue spam:** semantic resolved/already-recorded filtering plus existing deterministic fingerprint dedupe.
- **Stale receipt satisfies later work:** bind evidence to current task execution identity using existing lifecycle provenance.
- **Sensitive leakage:** raw evidence stays local; existing sanitization remains authoritative for GitHub output.
- **GitHub outage:** positive findings remain pending locally and do not redefine safe publication as failed.
- **AI self-modification:** process review cannot create Development Backlog tasks or implementation PRs.
