## Context

`archive_change` (non-finalize) already distinguishes `managed_candidate(root)` and, for a candidate, reuses review and selected-check evidence. After the archive the candidate predicate is false (`provenance.lifecycle != "active"` and no re-admission), so `finish` routes it to terminal publication, whose `require_publication_task_base` accepts behind-mergeable only for `queue_integrated` tasks. The single-child advance hands off an active child through `finish_task.py` (`_publish_active_child`), which already gets behind-mergeable.

## Decisions

- **D1=A, refuse.** In `archive_change`, when not `finalize`, the lifecycle mode is `coordinator` and `managed_candidate(root)` is true, raise `SystemExit` before the privacy gate, naming the change and the next commands (`python3 scripts/execute_requirement.py advance --requirement <BR>` for a Requirement child, else `python3 scripts/dogfood_task.py finish`) and that finalize archives. No fallback: the gate does not archive anyway or downgrade. `--finalize` is unchanged. The `coordinator_managed` branches of the developer archive become unreachable and are removed.
- **D2=A, generated files only.** `agent_friction.current_task_content` builds the managed proof with `exclude` = files declared generated at the merge base of `HEAD` and `origin/<main>` (the existing `_declared_generated_at_base`, which raises when unreadable) and scope `friction-checkpoint-v1`. Equivalence across a base move is unchanged (`equivalent_proofs`: same digest and scope, ancestor base, no task path touched by main).
- **Spec.** completion-lifecycle and platform-lifecycle get one ADDED requirement each (≤ 500 characters).

## Risks

- A checkpoint recorded before this change has the old scope and is stale once; the message names the checkpoint command.
- A developer used to archiving before handoff now gets the refusal; the message names the command.
