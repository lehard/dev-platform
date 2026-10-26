## Context

- Portable managed: archive writes `<change>/automated-checks.json` with `gate_task_content` (review-scoped `content_identity`); finish calls `require_automated_evidence` then `validate_or_reuse` -> `automated_evidence_reuse`, which rejects any base other than the recorded one.
- Coordinator managed: `pr_review_gate.handoff_gates` accepts evidence by `equivalent_proofs(recorded gate, current gate)`; finish runs no checks.
- Quick, either mode: `validate_or_reuse` always calls `run_checks` (`select_checks --execute` without evidence).
- `equivalent_proofs` compares digest and scope (the digest covers own-path blob ids only, not the base); across a base move it requires the old base to be an ancestor of the new and no task path to be changed between them.

## Decisions

- **One rule, the existing proof.** Reuse uses `equivalent_proofs`, the proof the coordinator handoff already trusts, rather than a second notion of "own diff unchanged". A main advance that touches a task path is not reusable even if it merges cleanly; the task's result there could differ. Equal base stays the trivial case.
- **Preflight decides publishability, reuse decides only rerun.** Reuse no longer checks that HEAD contains main: finish's preflight freshness blocker already refuses heads that must reconcile, and accepts a queue-integrated behind-mergeable head. A reused decision never relaxes that gate.
- **Quick evidence is machine-local.** A quick task has no change directory. Its evidence lives in the worktree's own git directory (`--git-path dev-platform/check-evidence.json`), outside the tree, so it never dirties the checkout or reaches a PR and is unique per worktree. It is a reuse hint for the same machine; required CI on the exact head remains the gate. Written only on explicit request (`--task-evidence`), which finish passes for a quick task.
- **Quick proof.** `quick_content_identity(root)` = `content_identity(root, [], exclude=declared generated files at the merge base, scope="quick-task-v1")`. Refused on a managed checkout, and a missing proof (no merge base) fails the evidence write explicitly.
- **Absent quick evidence is a reason, not an error.** The first finish of a quick task has nothing to reuse; it prints `not-reusable: no recorded quick-task evidence` and runs the checks, which then record evidence.

## Risks

- A stale machine-local quick evidence file from an earlier head: the content proof binds it to own-path blobs, so any task-content change makes it not reusable.
- Selection drift: the current required selection must be fully covered, so a newly required command forces a run.
