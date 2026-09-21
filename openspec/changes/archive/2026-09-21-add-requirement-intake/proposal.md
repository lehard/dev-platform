# Proposal: Add a human-facing Business Requirement object

## Why

The resumable pre-authoring orchestrator (#129) still has no human-facing entry point: fixing a business requirement today means directly authoring a managed OpenSpec change, and a requirement that legitimately needs several internal changes turns into several unrelated cards on the main Development Backlog board. Add a durable, business-language Requirement object as the one thing a human normally manages, wired to #129 for analysis and to the existing managed OpenSpec lifecycle for implementation, without introducing a second backlog or status machine.

## What Changes

- Add a Requirement Issue contract (GitHub Issue, `type:requirement` label, business-language body, stable `requirement-<N>` identity, machine-readable children block).
- Add `scripts/requirement_intake.py`: `create` (author a Requirement without OpenSpec), `start` (bridge a Requirement into `orchestrate_pre_authoring.py init`), `link-child` (attach a materialized internal managed OpenSpec Issue to its parent Requirement), `aggregate` (read-through status derived from each linked child's real Project status via the existing `managed_project_status.observe()`).
- Document the exact, minimal activation delta the ChatGPT Project protocol chat needs to switch `"зафиксируй"` from authoring an OpenSpec change directly to authoring a Requirement first -- without activating it here.

## Success Evidence

A business requirement can be recorded as one Requirement Issue with no OpenSpec artifact; `orchestrate_pre_authoring.py` can resume pre-authoring from it; a handoff-ready intent's resulting internal managed OpenSpec Issue links back to its Requirement and is labeled distinctly from it; `aggregate` reports a Requirement's status derived only from its children's real lifecycle state; existing quick-task and direct managed-task/OpenSpec paths are unchanged.

## Dependencies

Requires Development Backlog #129 (resumable pre-authoring orchestrator).
