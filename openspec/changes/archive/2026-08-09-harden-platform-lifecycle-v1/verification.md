# Verification — harden-platform-lifecycle-v1

This review applies the current OpenSpec `/opsx:verify` dimensions — completeness, correctness and coherence — to this change. The literal slash workflow is not invokable from the current GitHub connector session, so this document records the equivalent semantic review rather than claiming the command itself was executed.

## Completeness

All six delta requirements have implementation surfaces and validation evidence:

1. **GitHub-aware task lifecycle** — `project_sync.py`, `agent_doctor.py`, `start_task.py`, `finish_task.py`, `project_publish.py`; Git lifecycle tests cover behind/ahead/diverged states and guarded publication.
2. **Configurable publication modes** — Copier/config expose `pr` and `direct`; PR mode uses authenticated `gh` without auto-merge; direct mode re-fetches and forbids force push.
3. **Composable workflow profiles** — one Copier template renders `light`, `standard`, and `multi-agent`; CI renders all three; worktree/board rules are conditional.
4. **OpenSpec contract coherence** — root/template AGENTS, OpenSpec config and workflow docs encode current-spec + active-delta ownership, no-silent-divergence routing, and verify-before-archive policy.
5. **Versioned platform dependency** — generated CI uses `platform_ci_ref`; tests and CI reject `project-ci.yml@main`; the final v1 factory default is the exact validated release SHA.
6. **Deliberate learning promotion** — friction events have IDs; `promote` requires explicit action, only accepts platform scope, omits raw evidence, sanitizes obvious secret patterns, supports dry-run, and creates the central issue through authenticated `gh`.

The append-only `release-v1.0.0` alias was created at validated commit `b4a95a26c7caf14dd5b0d44da0237dcd70bf8715`. The factory default is pinned to that exact SHA.

## Correctness

Evidence before release:

- shared platform scripts compile;
- 12 local/CI unit and integration tests cover template and Git lifecycle behavior, including a simulated authenticated `standard + pr` publication path that returns the integration copy to `main`;
- temporary Git remotes verify fast-forward sync, refusal of local-ahead start, safe direct publication, refusal on real divergence, standard/direct local integration + publication, and PR branch publication behavior;
- final code PR CI run `31210780560` passed for `light/direct`, `standard/pr`, and `multi-agent/pr`;
- each profile rendered through real Copier, compiled generated scripts and ran the generated platform doctor;
- downstream workflow templates contain no `@main` reference.

Semantic review found one issue after an earlier green CI: current OpenSpec 1.6 generated verify skills are named `openspec-verify-change`, not `openspec-verify`. `platform_doctor.py` was corrected to detect `openspec-verify-change`, and the full profile matrix passed again after that correction.

A second lifecycle review found that `standard + pr` returned from PR creation while leaving the local integration copy checked out on the feature branch. That would have required a manual `git switch main` before the next task and violated zero-hand-off. `finish_task.py` now switches the standard integration copy back to `main` after a successful PR publication, with a simulated-`gh` integration test covering the behavior.

## Coherence

Implementation matches the active proposal/design:

- GitHub publication is now a platform responsibility rather than a human hand-off;
- conflict/divergence handling fails closed instead of silently reconciling;
- profiles compose capabilities rather than forking templates;
- OpenSpec policy distinguishes process constraints, accepted current behavior and active approved delta;
- project-specific QA remains separate from semantic OpenSpec verification;
- exact-SHA release pinning eliminates the silent `@main` update channel and removes mutability from downstream reusable CI execution;
- promotion remains deliberate and sanitized rather than automatically uploading local friction.

No Jara_Fin files or workflows are changed by this OpenSpec change.

## Release status

Platform v1.0.0 implementation was merged at `b4a95a26c7caf14dd5b0d44da0237dcd70bf8715`. The append-only `release-v1.0.0` alias points to that commit, and new generated projects pin reusable CI to the exact same SHA.
