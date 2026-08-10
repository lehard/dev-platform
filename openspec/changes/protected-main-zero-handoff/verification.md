# Verification

OpenSpec-Verify: PASS
Verification-Method: manual completeness/correctness/coherence review plus GitHub Actions Platform CI run 31365251975

## Completeness

- Proposal goal is implemented: protected-main work has a PR-first zero-hand-off path and direct protected-main publication is rejected.
- Project factory exposes `protected_main` and `pr_merge_mode` and defaults feature-capable profiles to protected PR publication with automatic task merge.
- `agent_doctor.py` and `finish_task.py` perform early configuration/authentication preflight.
- `project_publish.py` separates feature-branch push from GitHub PR API actions, waits required checks, and merges without `--admin` or any protection bypass.
- Local `main` synchronization occurs only after the remote PR merge succeeds.
- Explicit manual PR mode remains available and cross-repository rollout remains separately reviewed.
- Generated docs/agent rules describe the same lifecycle and credential requirements.

## Correctness

GitHub Actions Platform CI run `31365251975` passed after the final implementation and regression additions. The successful job included:

- shared-script compilation;
- managed-project registry validation;
- all unit tests;
- OpenSpec lifecycle hygiene;
- strict OpenSpec validation;
- Copier installation and all three profile renders;
- Copier upgrade smoke tests;
- mature project harness adoption smoke;
- project-harness smart-update fallback smoke.

New lifecycle regression coverage verifies:

- automatic PR check wait + remote merge + local-main synchronization;
- failed cloud checks leave local and remote main unchanged;
- protected direct publication fails before local integration;
- missing PR API authentication fails normal `finish_task.py` before feature-branch publication;
- direct `project_publish.py --mode pr` keeps branch push independent and reports incomplete PR API publication;
- `project_publish.py` itself refuses declared protected-main direct publication.

## Coherence review

The proposal, design, lifecycle delta, project-factory delta, implementation and generated guidance were compared after implementation. One material review finding was identified: the first implementation guarded protected direct publication in `finish_task.py` but a direct invocation of `project_publish.py --mode direct` could still attempt the push. That gap was fixed before this PASS receipt and covered by a dedicated contract test.

A second implementation detail discovered during apply was recorded back into `design.md`: when `gh` is not independently authenticated, the platform may non-persistently reuse an existing GitHub HTTPS credential through `git credential fill`, validate it as process-local `GH_TOKEN`, and never log or persist it. SSH-only hosts still require a one-time GitHub API credential setup.

The downstream migration is intentionally documented as post-release operational rollout rather than an active-change archive prerequisite: the immutable platform release must exist before managed Copier rollout can target it, and preserved/project-owned files require reviewed per-repository updates.

No unresolved material OpenSpec findings remain.