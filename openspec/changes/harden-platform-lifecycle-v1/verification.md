# Verification — harden-platform-lifecycle-v1

This review applies the current OpenSpec `/opsx:verify` dimensions — completeness, correctness and coherence — to this change. The literal slash workflow is not invokable from the current GitHub connector session, so this document records the equivalent semantic review rather than claiming the command itself was executed.

## Completeness

All six delta requirements have implementation surfaces and validation evidence:

1. **GitHub-aware task lifecycle** — `project_sync.py`, `agent_doctor.py`, `start_task.py`, `finish_task.py`, `project_publish.py`; Git lifecycle tests cover behind/ahead/diverged states and guarded publication.
2. **Configurable publication modes** — Copier/config expose `pr` and `direct`; PR mode uses authenticated `gh` without auto-merge; direct mode re-fetches and forbids force push.
3. **Composable workflow profiles** — one Copier template renders `light`, `standard`, and `multi-agent`; CI renders all three; worktree/board rules are conditional.
4. **OpenSpec contract coherence** — root/template AGENTS, OpenSpec config and workflow docs encode current-spec + active-delta ownership, no-silent-divergence routing, and verify-before-archive policy.
5. **Versioned platform dependency** — generated CI uses `platform_ci_ref`; tests and CI reject `project-ci.yml@main`.
6. **Deliberate learning promotion** — friction events have IDs; `promote` requires explicit action, only accepts platform scope, omits raw evidence, sanitizes obvious secret patterns, supports dry-run, and creates the central issue through authenticated `gh`.

The only intentionally post-merge item is creation of append-only `release-v1.0.0` at the validated main commit.

## Correctness

Evidence before final merge:

- shared platform scripts compile;
- 11 local unit/integration tests pass;
- temporary Git remotes verify fast-forward sync, refusal of local-ahead start, safe direct publication, refusal on real divergence, and standard/direct local integration + publication;
- PR CI successfully rendered and compiled all three profiles;
- generated doctors ran in the profile matrix;
- downstream workflow templates contain no `@main` reference.

One semantic review issue was found after the first green CI: current OpenSpec 1.6 generated verify skills are named `openspec-verify-change`, not `openspec-verify`. `platform_doctor.py` was corrected to detect `openspec-verify-change` before merge. Final PR CI must pass again after this correction.

## Coherence

Implementation matches the active proposal/design:

- GitHub publication is now a platform responsibility rather than a human hand-off;
- conflict/divergence handling fails closed instead of silently reconciling;
- profiles compose capabilities rather than forking templates;
- OpenSpec policy distinguishes process constraints, accepted current behavior and active approved delta;
- project-specific QA remains separate from semantic OpenSpec verification;
- release pinning eliminates the silent `@main` update channel;
- promotion remains deliberate and sanitized rather than automatically uploading local friction.

No Jara_Fin files or workflows are changed by this OpenSpec change.

## Remaining release gate

After this verification fix, PR CI must be green. Then the PR may be merged and `release-v1.0.0` created at the resulting validated main commit. The release ref must never be moved.
