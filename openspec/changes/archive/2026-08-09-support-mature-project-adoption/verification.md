# Verification

OpenSpec-Verify: PASS
Verification-Method: semantic completeness/correctness/coherence review plus successful Platform CI run 182

## Evidence

- Repository state and lifecycle ownership are derived independently; fresh defaults remain `standard + platform + direct`, while simple existing repositories remain `standard + platform + pr`.
- Deterministic project-harness markers select `harness_mode=project` only for a coherent lifecycle surface; repository size alone never selects project ownership, and ambiguous collisions fail closed before Copier mutation.
- The Jara_Fin-like acceptance fixture derives `existing + multi-agent + project + pr` with auditable reasons and preserves project-owned AGENTS/OpenSpec guidance, check selection, board/worktree/merge lifecycle and existing project CI byte-for-byte.
- Project-harness adoption records reviewed lifecycle paths in `project_required_files`; platform doctor validates those requirements without requiring platform-owned multi-agent board/worktree/Git-hook files.
- Adoption validation and generated Dev Platform CI do not call a project-owned selector with `--execute`/`--full` and do not install arbitrary product dependencies; repository CI remains authoritative for product/application checks.
- Shared platform/OpenSpec hygiene remains active in project-harness mode: platform doctor, OpenSpec lifecycle hygiene and strict OpenSpec structural validation are still enforced.
- Platform-owned start/finish wrappers already reject `harness_mode=project` with explicit instructions to use repository-owned lifecycle entrypoints.
- `python3 scripts/dev.py ready` is exercised twice in the mature acceptance fixture and does not mutate preserved project-owned lifecycle files.
- One-command onboarding reports the derived workflow/harness/publish plan and reasons, leaves first-pass existing migrations review-only, and excludes them from managed promotion until the adoption PR is merged and onboarding is rerun.
- Platform CI run 182 completed successfully across light, standard and multi-agent matrices, including unit tests, compile checks, registry validation, strict OpenSpec validation, factory rendering, Copier upgrade smoke, mature project-harness acceptance and guarded recopy smoke.
- Documentation now explains automatic mature-harness detection, CI ownership boundaries, ambiguous collision behavior and the manual fallback.

## Findings

No material completeness, correctness or coherence findings remain. The implementation preserves the existing fresh-project fast path and ordinary reviewed managed-rollout boundary while adding the project-owned mature migration path required by the change.
