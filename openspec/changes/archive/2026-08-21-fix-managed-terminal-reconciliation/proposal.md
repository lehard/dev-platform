# Proposal: Fix terminal reconciliation for managed project-harness PRs

## Why

`planner-agent-lab` declared Dev Platform `v1.4.36`, but its preserved
project-owned `finish_task.py` lacked the terminal Project reconciliation that
the matching platform template already supplied. PR #56 therefore merged while
Development Backlog #59 remained `In progress` and open. Version metadata alone
must not be accepted as lifecycle conformance for a recognized project harness.

## What changes

- Extend the reviewed Planner compatibility migration so exact merged-PR proof
  leads to idempotent terminal reconciliation for only the bound
  `source_issue + change` identity.
- Preserve and expose a resumable pending-reconciliation state when the
  Project/Issue mutation fails after a confirmed merge.
- Make rollout conformance reject a Planner-like harness that cannot prove this
  terminal behavior, without overwriting unknown project-owned bytes.
- Add regression tests for normal auto-merge, merged-PR retry, mutation failure
  followed by retry, and delayed check registration.

## Impact

This changes reusable managed-task delivery and rollout safety only. Product
code and Planner autonomous-repair behavior are out of scope.
