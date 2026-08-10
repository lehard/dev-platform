# Verification

OpenSpec-Verify: PASS
Verification-Method: manual completeness/correctness/coherence review plus exact-head GitHub Actions Platform CI run 31366690978

## Completeness

- The protected-main publication dead-end is addressed at platform level rather than by repository-specific bypasses.
- Project factory configuration explicitly records `protected_main` and `pr_merge_mode`, with protected PR/auto defaults for feature-capable profiles.
- `agent_doctor.py` and `finish_task.py` detect invalid protected/direct configuration and missing GitHub PR API authentication before local integration.
- `project_publish.py` separates feature-branch push from PR API actions, waits required PR checks, and merges through GitHub without `--admin` or branch-protection bypass.
- Local `main` synchronization happens only after the remote PR merge succeeds.
- `pr_merge_mode=manual` remains available and cross-repository Dev Platform rollout remains separately reviewed.
- Generated agent and workflow guidance matches the implemented lifecycle.

## Correctness

GitHub Actions Platform CI run `31366690978` completed successfully on commit `506d15882a520328655490a9be121a25e67df479`, after reconciliation with the v1.4.9 safety-hardened baseline and PR #49 workflow/config consistency hardening.

The successful platform CI exercises compilation, managed-project validation, unit tests, OpenSpec lifecycle/strict validation, Copier profile renders, upgrade smoke tests, mature project harness adoption smoke, and project-harness update smoke.

Dedicated regressions additionally cover:

- protected direct publication rejected before local-main mutation;
- automatic PR check wait, remote merge, and only-then local-main synchronization;
- failed cloud checks leave local and remote `main` unchanged;
- missing GitHub PR API authentication blocks normal `finish_task.py` before feature-branch publication;
- direct `project_publish.py --mode pr` can leave a validated branch safely pushed while reporting incomplete PR API publication;
- `project_publish.py` itself refuses direct publication when `protected_main=true`.

## Coherence

The proposal, design, lifecycle delta, project-factory delta, implementation, tests, and generated guidance were compared after implementation.

Two material implementation findings were resolved before this PASS:

1. The first implementation guarded protected direct publication only in `finish_task.py`; direct invocation of `project_publish.py --mode direct` could still attempt the push. `project_publish.py` now independently refuses declared protected-main direct publication and a contract test covers it.
2. GitHub CLI authentication could duplicate credentials already usable for HTTPS git. The design and implementation now allow non-persistent reuse of an existing GitHub HTTPS credential via `git credential fill` as process-local `GH_TOKEN`, while never logging or writing the token. SSH-only hosts still require a one-time `gh auth login` or token environment setup.

The implementation was also reviewed specifically against v1.4.9 hardening. It preserves the explicit `DEV_PLATFORM_ALLOW_NO_CHECKS` override requirement, the `DEV_PLATFORM_VALIDATED_DIRECT_PUBLISH` guard, high-impact check escalation, and workflow/config consistency validation. The new PR merge path does not use any admin/bypass option.

Downstream migration remains a post-release operational step because the immutable Dev Platform release must exist before managed Copier rollout can target it, and `.dev-platform.toml` / project-owned harness files require explicit reviewed updates in existing repositories.

No unresolved material OpenSpec findings remain.