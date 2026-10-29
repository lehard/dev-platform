OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the three spec deltas, proposal, design and tasks; targeted unit tests (test_lifecycle_preflight, test_blocking_gates, test_select_checks, test_managed_checkout_identity, test_task_freshness, test_git_lifecycle, test_merge_lifecycle_resilience, test_protected_main_zero_handoff, test_publication_recovery_cli, test_portable_finish_check_reuse, test_finish_explicit_fallbacks); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Direct handoff (deterministic depth, no ADD): the requirement fixes the contract and the preflight reuses existing gate functions.
- The selector keeps its inline task-freshness gate (it records the behind-mergeable contract in evidence) and the preflight declares `task-base` evaluated there; `finish` keeps its consolidated blocker list for freshness and scope on the non-handoff path. The registry still runs the shared-workspace and project cheap-gate conditions at both entries, and all four on the developer-handoff path.
- The board condition keeps the applicability the old scope gate had; a narrow selection without handoff evidence is declared not applicable.

## Completeness

- `lifecycle_preflight.py` implements the four conditions, prints each result and reports all refusals together; `select_checks.py --execute` and `finish_task.py` call it before any expensive operation.
- Own-account permission findings are repaired and reported (`repaired`); another account's are refused with owner and `chgrp`/`chmod` command: `SharedWorkspaceConditionTests`.
- A missing claim is refused with the gate's message and the `agent_board.py admit` command; a failing project cheap gate (the writer-guard baseline test, configured in `dev-platform/checks.toml`) refuses before the full set: `BoardClaimAndScopeTests`, `ProjectCheapGatesTests`.
- Every catalog gate has exactly one of `preflight`/`no_preflight`, enforced by the loader and by `PreflightRegistryTests` (ids resolve, conditions list exactly the gates that name them, justification is a sentence).
- Gate and condition give the same answer because the condition calls the gate function; asserted for claim and for freshness (`test_a_missing_claim_is_refused_with_the_gate_message...`, `TaskBaseTests`).

## Correctness

- No gate semantics changed: existing messages for freshness, scope and finish blockers are unchanged (the existing suites above pass unmodified except fixtures that copy scripts and one import-location assertion).
- A condition that cannot be evaluated refuses; nothing passes by default. Waivers are printed with their reason.

## Coherence

- Spec deltas, design, tasks and `docs/engineering/agent-workflow.md` describe the same flow; the platform manifest and protected surface include the new script.

## Not verified / limits

- Foreign-owner refusal is covered with a mocked owner; no second OS account exists on this machine (multi-account behaviour stays BR-469).
- The git-metadata setgid case is covered by the shared-workspace audit already registering worktree metadata; not reproduced on a real new worktree.
- The manifest-staleness and protected-surface checks stay in the full validation set (manifest check runs before the test run); they are not in the preflight.
