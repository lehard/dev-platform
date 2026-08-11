# Tasks

- [x] 1. Replace/extend the containment snapshot with content-aware fingerprints for dirty tracked/index/untracked state; add regressions for same-status content mutation, unchanged dirty state, untracked mutation, create/delete, and snapshot failure.
- [x] 2. Add one supported platform guarded entrypoint for write-capable delegation that validates `assigned_worktree`, applies an explicit enforcement tier, launches with `cwd=assigned_worktree`, and always runs the post-check before returning.
- [x] 3. Implement the platform-controlled Codex adapter using the supported OS writable-root sandbox for `assigned_worktree`; fail closed on unavailable requested hard containment and test that no silent hard->detection downgrade is mislabeled.
- [x] 4. Implement Claude Code hook-assisted prevention for structured filesystem write tools in platform-controlled child/session configuration; keep shell-capable mode detection-only unless a real OS sandbox is proven, and test allow/deny path resolution.
- [x] 5. Enforce the dirty-integration rule: detection-only write delegation must not launch over pre-existing uncommitted integration state; hard-contained runs may proceed but still receive the content-aware post-check.
- [x] 6. Update generated/platform agent workflow guidance to require the guarded path for platform-contained delegated writes without vendoring OpenSpec-generated Claude/Codex skills or taking ownership of unrelated tracked agent settings.
- [x] 7. Add failure-path and friction tests: child non-zero/cancellation still runs post-check; violation records locally without GitHub auth; no containment path auto-stashes/resets/cleans/deletes integration state.
- [x] 8a. Run Project Factory render/compile plus existing managed platform-harness upgrade/adoption/recopy smokes locally (`tests/upgrade_smoke.py` for all three profiles, `tests/project_harness_adoption_smoke.py`, `tests/rollout_recopy_smoke.py`).
- [ ] 8b. After a stable platform release includes this change, perform one real guarded delegated-write acceptance in a managed consumer (prefer Cuby) covering both an allowed in-worktree write and a blocked/detected out-of-scope attempt appropriate to the runtime tier. Blocked on: a published immutable release containing this change, plus a real Cuby session willing to exercise it.
- [ ] 9. Run platform validation and semantic OpenSpec verification, record `OpenSpec-Verify: PASS` with the real method in `verification.md`, archive via `python3 template/scripts/openspec_lifecycle.py archive wire-runtime-delegation-containment`, then publish through protected main. Blocked on 8b: archiving before a real downstream acceptance would misrepresent the change as fully accepted when it has only been locally validated.

## Logical commit boundaries

1. Content-aware snapshot + tests.
2. Guarded delegation entrypoint + runtime adapters + tests.
3. Agent guidance/render compatibility.
4. Downstream acceptance evidence + verification/archive.