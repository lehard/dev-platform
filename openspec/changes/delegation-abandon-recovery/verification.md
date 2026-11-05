# Verification: delegation-abandon-recovery

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta spec against the implementation, scenario by scenario, with canonical regression tests. No opsx tool invocation is claimed.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- Closure: `close-abandoned-delegation --reason` closes an open Codex delegation with outcome `abandoned`, `closed_at`, `task_content_post` and an `abandonment` object holding the reason and observation. It creates no execution evidence, so the archive routing gate still refuses the route until a new one finishes.
- Evidence: `lsof -d cwd`, filtered to the assigned worktree, excluding the caller's process ancestry. A live process is named. A missing or failing `lsof`, or a failing `ps`, refuses naming the cause. Every refusal writes nothing.
- Other states: no delegation, a Claude delegation, a closed delegation or one with an execution refuse, naming the state and the supported path.
- Rerouting: `prepare` accepts the closure and records `rerouted_from` while task content equals the recorded post-content; content changed after the closure stays refused. `escalate` treats an abandoned delegation as a child that ran. The recovery postcheck accepts only a verified fast-forward of integration for a dead writer.
- Output: `dispatch-codex`, behind `route-codex`, prints the writer before launch and returns it: the Codex child on R1 and R2, the retained parent on R3.

## Provenance

Draft notes for this change were prepared before this child was started and routed, on the same base. The coordinator ruled that a deviation. Implementation happened only after `advance` started the child and `route-claude` recorded the route, in this worktree, in stages, with each change checked against the code at the child's base and covered by the tests below.

## Evidence

- Selected checks passed on committed head 107b7fa4; record in `automated-checks.json`.
- `openspec validate --all --strict`: 52 passed, 0 failed. `openspec_lifecycle.py check`: OK. Ruff and manifest passed.
- New tests cover closure and reroute, content changed after closure, escalation, a named live process, a real process observed through `lsof`, the caller's ancestry, unobservable liveness, every refused state, record validation and the writer statement.

## Not verified

- No live Codex child was killed; the closure runs on a constructed open delegation.
- Output of `route-codex` is tested at `_writer_statement`, not through a real Codex launch.
- On a host where `lsof` cannot read other users' processes, those processes are not observed; a worktree writer runs as the same user, so this is accepted.
