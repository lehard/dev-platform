## Why

BR-415 requires stable-release lifecycle hardening. `requirement_intake.materialize_handoff` creates technical children through `managed_task.create_task`, which labels the child from `managed_task.authoring_config(root)` (the current checkout's `[development_backlog]` table). The parent Requirement's own `project:*` label and Backlog repository are never consulted, and the read-back (`verify_published_managed_task`, then the linkage checks) proves the child against that same checkout config, not against the parent. A mismatch between checkout configuration and Requirement therefore yields a child under a contradictory `project:*` label (or in a different repository, detected only after publication) that is still reported as successfully linked. `link_child` adds `type:internal-change` but never reads it back.

## What Changes

- Add a pre-publication routing resolution in `template/scripts/requirement_intake.py` that reads the exact parent Requirement's labels (exactly one `project:*`), its Backlog repository and the committed target `[development_backlog]` configuration, and requires all of them to agree. Any contradiction, missing or ambiguous input fails with a named error before `create_task` is called.
- Verify, before reporting materialization success and on every retry, that the child carries exactly the parent's `project:*` label, `type:internal-change`, and the parent back-reference/checklist link. A mismatch fails with the child reference, expected and found labels, and repair guidance.
- An already existing exact-handoff child with a contradictory `project:*` label is reported as a visible error; the retry path never removes or replaces a conflicting label. Only a missing `type:internal-change` is completed (existing `link_child` behavior), then re-verified.
- Extend `link_child` so its label write is read back, so the standalone `link-child` command gives the same proof.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-workflow`: Verified technical child project routing during handoff materialization and child linking.

## Impact

`template/scripts/requirement_intake.py` (materialize_handoff, link_child, new routing helpers), minimal reuse of `template/scripts/managed_task.py` (`issue_labels`, `AuthoringConfig`, `validate_backlog_labels`); `tests/test_requirement_intake.py` and `tests/test_managed_task.py` regression coverage; shipped template parity via the existing source/template checks. No schema, label vocabulary or CLI flag changes.

## Success Criteria

A child is never created or accepted under a `project:*` label or Backlog repository that contradicts its parent Requirement; successful output implies read-back proof of project label, internal-change label and parent link; contradictory pre-existing children surface as errors naming the Issue and repair guidance.

## Non-goals

Independent pre-release Requirements (#386, #376, #380/#382, #367, #403, #391), stable tagging, fleet rollout, remote reviewer/TeamAI, relabeling tooling for historical children, changing `managed_task.py create` for direct technical managed tasks, and unrelated cleanup.
