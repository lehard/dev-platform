OpenSpec-Verify: PASS
Verification-Method: supervisor semantic review of proposal, design, delta spec and implementation; executable regressions; independent review (Claude reviewer); real-machine installation
Independent-Review-Evidence: independent-review-request.json
Automated-Checks-Evidence: automated-checks.json

Implementation of the opt-in shared local workspace runtime (`template/scripts/local_workspace.py`)
was reviewed against the delta spec: bounded source/worktree audit with owner-only repair,
hook composition preserving existing hooks, external registry with identity-scoped discovery,
idempotent runtime update, cooperative launcher and per-user LaunchAgent, and opt-in lifecycle
source admission. Source repair never descends into nested checkouts, refuses source roots inside
them, and never mutates entries it cannot open; inherited `core.hooksPath` is resolved per
invoking user; the policy probe ignores inherited `GIT_*`.

Checks actually run (final candidate):

- `python3 -m unittest tests.test_local_workspace`: 40 passed (incl. regressions for each
  independent-review finding: nested checkouts, nested source roots, tracked paths under nested
  checkouts, write-only owned sources, foreign unreadable diagnostics, tilde/inherited hooksPath,
  invalid inherited GIT_DIR).
- `python3 -m unittest tests.test_shared_writer_guard`: passed after reviewing the added
  `_open` write-only descriptor site (baseline 3).
- `python3 scripts/run_test_groups.py --all` on the pre-merge-fix head: only
  `test_shared_writer_guard` failed (baseline count), since repaired and re-run green; all other
  groups passed.
- Independent review: spec-fidelity and engineering-quality perspectives ran with the Claude
  provider (the Codex reviewer was rate-limited; provider set locally per operator direction).
  Earlier Codex rounds found and drove fixes for 10 material findings; the final Claude round
  reports no material findings, only 6 advisory items (hook audit on every hook, shared runtime
  not re-verified against its digest, fail-closed outside workspace roots, doc references source
  path, dead assignment) left as follow-up.

Real-machine acceptance (identity lehard, uid 501; group `staff`):

- Registry and shared runtime installed at `/Users/Shared/Workspace/.dev-platform-local-workspace`
  (operator-local; no tracked machine paths). Per-user LaunchAgent installed and loaded.
- Cuby attached. Restrictive 0600 file and an atomic replacement were detected by `check` and
  repaired to group read/write by `repair`; directory setgid confirmed.
- dev-platform, terrazzo_mvp and Jara_Fin are NOT yet attached: they hold `code`-owned
  (uid 505) directories without setgid and a few 0644 files. The runtime reported the exact paths
  and the owner action; attachment is correctly withheld until `code` runs sync. dev-platform's
  existing operator `core.hooksPath` was left untouched.
- planner-agent-lab has no local checkout (reported unavailable).

Capability limits: no second-identity session (`code`) is available here and sudo is unavailable,
so two-user execution, `code`'s LaunchAgent and the pending attachments are unproven; the other
account must run `python3 /Users/Shared/Workspace/.dev-platform-local-workspace/local_workspace.py
sync --registry /Users/Shared/Workspace/.dev-platform-local-workspace/registry.json` and
`install-agent`. `runtime_source` auto-update is not configured until this change is on main.
