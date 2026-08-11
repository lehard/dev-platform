# Tasks

- [ ] 1. Replace/extend the containment snapshot with content-aware fingerprints for dirty tracked/index/untracked state; add regressions for same-status content mutation, unchanged dirty state, untracked mutation, create/delete, and snapshot failure.
- [ ] 2. Add one supported platform guarded entrypoint for write-capable delegation that validates `assigned_worktree`, applies an explicit enforcement tier, launches with `cwd=assigned_worktree`, and always runs the post-check before returning.
- [ ] 3. Implement the platform-controlled Codex adapter using the supported OS writable-root sandbox for `assigned_worktree`; fail closed on unavailable requested hard containment and test that no silent hard->detection downgrade is mislabeled.
- [ ] 4. Implement Claude Code hook-assisted prevention for structured filesystem write tools in platform-controlled child/session configuration; keep shell-capable mode detection-only unless a real OS sandbox is proven, and test allow/deny path resolution.
- [ ] 5. Enforce the dirty-integration rule: detection-only write delegation must not launch over pre-existing uncommitted integration state; hard-contained runs may proceed but still receive the content-aware post-check.
- [ ] 6. Update generated/platform agent workflow guidance to require the guarded path for platform-contained delegated writes without vendoring OpenSpec-generated Claude/Codex skills or taking ownership of unrelated tracked agent settings.
- [ ] 7. Add failure-path and friction tests: child non-zero/cancellation still runs post-check; violation records locally without GitHub auth; no containment path auto-stashes/resets/cleans/deletes integration state.
- [ ] 8. Run Project Factory render/compile plus an existing managed platform-harness upgrade smoke. After release, perform one real guarded delegated-write acceptance in a managed consumer (prefer Cuby) covering both an allowed in-worktree write and a blocked/detected out-of-scope attempt appropriate to the runtime tier.
- [ ] 9. Run platform validation and semantic OpenSpec verification, record `OpenSpec-Verify: PASS` with the real method in `verification.md`, archive via `python3 template/scripts/openspec_lifecycle.py archive wire-runtime-delegation-containment`, then publish through protected main.

## Logical commit boundaries

1. Content-aware snapshot + tests.
2. Guarded delegation entrypoint + runtime adapters + tests.
3. Agent guidance/render compatibility.
4. Downstream acceptance evidence + verification/archive.