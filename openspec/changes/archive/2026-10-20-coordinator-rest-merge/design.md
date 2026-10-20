## Context

- `publication_queue.py` (integration step, ~line 2050) runs `gh pr merge N --squash --match-head-commit <head>`, then reads `_pr(...)["merged"]`; a non-zero exit becomes `{"state": "waiting", "reason": "protected merge refused; will re-evaluate: <stderr[:300]>"}`.
- gh evaluates `mergeStateStatus` before calling the API and refuses `BLOCKED` without `--admin`/`--auto`. With the ruleset active, PR #647 (green, `MERGEABLE`) reported `BLOCKED`, and four queue runs refused it on the client.
- The REST merge endpoint accepts `sha`; GitHub returns 409 when the head differs and 405 when a rule or required check forbids the merge. Ruleset bypass for an Integration in `pull_request` mode applies to PR merges through this endpoint; classic required checks still apply to the non-admin App.

## Decisions

1. Replace the gh CLI merge with `gh api -X PUT repos/{repo}/pulls/{number}/merge -f merge_method=squash -f sha=<head>` through the same subprocess call shape (cwd, captured output, stdin closed). The authenticated identity and token are unchanged (the App installation token in CI).
2. Keep the result handling: read back `merged`; on non-zero exit report `protected merge refused; will re-evaluate: <bounded stderr>`. No retry with another strategy and no `--admin`.
3. Do not touch the existing post-merge `except QueueError: pass` around the merged transition; it is reported to the owner separately as a pre-existing swallowed error.

## Rejected alternatives

- `gh pr merge --admin`: requests an administrator override semantics; even if harmless for a non-admin App, it is the wrong intent and would merge red PRs for an admin identity.
- `--auto`: enrolls GitHub auto-merge, a second merge mechanism outside the coordinator's head-bound control.

## Risks and mitigations

- *Bypass still refused by GitHub.* Not verifiable without the App token locally; the parent operator step re-enables the ruleset and observes a real queue merge, rolling back on refusal.
- *Error text changes.* Tests cover the waiting reason with a REST error payload; no token appears in it.
