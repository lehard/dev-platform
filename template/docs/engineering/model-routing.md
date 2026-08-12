# Provider-local model routing

Managed work starts with a strong parent/supervisor. After `start_managed_task.py` materializes canonical OpenSpec in the task checkout, the parent performs a bounded semantic preflight and records the execution profile with `scripts/model_routing.py prepare`.

The profile is `routine`, `standard`, or `complex`. The user does not select the executor. The parent assesses uncertainty, blast radius, failure cost, verification difficulty, current-contract conflicts and material unknowns; a small expected diff is not enough to force a low-cost profile.

Concrete mappings are current runtime policy in `[model_routing]` in `.dev-platform.toml`, rather than data in a backlog issue or OpenSpec artifact. Update those mappings as provider model lineups change.

For Codex, `codex-argv` and `run-codex` require a proven native `workspace-write` sandbox for the assigned worktree. If that proof is unavailable, the tool reports the constraint and the parent retains the work or uses a separately reviewed fallback; it never claims delegation that did not occur.

For Claude Code, request the `claude-agent` definition and use its `isolation: worktree` setting. The supervisor runs `postcheck` after the child returns, reviews the child diff and executes the normal task checks. Native worktree isolation is the write boundary; the post-check protects integration/main as defense in depth.

Routine or standard work must escalate to the complex profile when it finds a material OpenSpec/current-spec conflict, unexpected cross-cutting impact or scope, low confidence, or repeated substantive verification failures. Use `scripts/model_routing.py escalate --reason "..."`; the hand-off retains the canonical change, worktree/diff and evidence rather than restarting the task.
