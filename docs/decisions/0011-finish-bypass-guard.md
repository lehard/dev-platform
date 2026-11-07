# DEC-0011: The required check refuses a head that bypassed finish

- **Status:** Current
- **Scope:** Delivery of this repository: the trace `finish` leaves and the `validate` step that reads it
- **Decision date:** 2026-11-07
- **Authored against revision:** `4ae5f9a2ab4d072b59b4954e902d8fe87106b28d`
- **Supersedes:** None
- **Superseded by:** None

## Accepted current decision

The coordinator accepted this rule on 2026-11-07 under the owner-delegated roadmap.

1. With `delivery_trace = true` in `[settings]` of `dev-platform/checks.toml`, `finish` makes the published head carry a `Dev-Platform-Finish` trailer holding the tree of that commit. It uses an empty commit after all its gates, and only when the head is not already valid.
2. An early step of `validate` checks the PR head, not the merge commit that checkout gives it, and reads Git only. It refuses a missing, repeated or wrong trailer and names the next command.
3. `reconcile` keeps the trace of a head that already had one. A head that had none stays without one, and a local fix it pushes gets one only from the next `finish`.
4. The list of exceptions is empty. The goal is an accidental bypass; a hand-copied trailer is outside it.
5. Projects are unchanged: the template has neither the setting nor the step.

## When the guard itself is wrong

The workflow and scripts of a `pull_request` run come from the tree of that PR, so GitHub protection settings never need to change.

- **The guard refuses valid heads:** fix it in a task and deliver through `finish`; the fix applies to its own PR.
- **`finish` cannot deliver either:** on a branch from main, delete the step `Refuse a head that bypassed finish` from `.github/workflows/ci.yml`, open it with `gh pr create`, and merge it with `gh pr merge --auto --squash`. Then repair `finish` and restore the step through a normal delivery.

The second way also lets any PR switch the guard off for itself, in plain sight in its diff. That is accepted, because the goal is an accidental bypass.

## Rejected and deferred alternatives

- **A marker in the PR body:** rejected. Editing a body does not rerun the check, so every new head would need the marker written before its push.
- **A separate Git ref per head:** rejected. It is not in the PR and needs cleanup.
- **A status posted by `finish`:** rejected. It needs a credential and a way to protect it, which is the service this goal does not justify.
- **Enabling it in `.dev-platform.toml`:** rejected. That file is machine-local, so a stale copy would stop writing the trace.

## Evidence

BR-1011. Every PR of this repository was opened by its owner; no bot opens PRs here and the repository's workflows open PRs only in projects. Since the core was simplified, only the DEC-0009 change itself went around `finish`.

## Revisit triggers

- A bot or another legitimate source starts opening PRs here.
- The guard refuses a legitimate delivery.
- The empty commit breaks a gate that binds the head hash instead of task content.

Probe edit after finish.
