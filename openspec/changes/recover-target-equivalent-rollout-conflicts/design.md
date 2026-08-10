# Design: Target-equivalent rollout conflict recovery

## Safety rule

A Copier rejection is recoverable automatically only when the rollout can prove before mutation that the downstream target file already has the exact bytes of the requested immutable platform release.

For `harness_mode=platform`, every rejected path must satisfy that proof. Any rejected file that differs from the target template remains a hard failure.

For `harness_mode=project`, the existing project-owned/reclaimed-path rules remain unchanged.

## Recovery sequence

1. Before `copier update`, fingerprint the narrow set of platform-owned files eligible for target-equivalent recovery against the exact checked-out release template.
2. Run normal smart Copier update with `.rej` conflicts enabled.
3. If there are no rejects, continue normally.
4. If `harness_mode=platform` and every reject target was in the pre-proven target-equivalent set, reset only the ephemeral rollout branch and run guarded `copier recopy --overwrite` from the same exact release.
5. Execute the newly rendered platform bootstrap once.
6. Verify that the recovered files still match the exact template and that `.dev-platform.toml` changed only in release metadata allowed by the existing rollout contract.
7. Run normal rollout validation and open the review PR.

## Initial recovery allowlist

The recovery set stays deliberately narrow rather than treating every template path as safe. It includes platform-owned lifecycle files that may already have been repaired downstream before a formal release rollout:

- `scripts/_platform_common.py`
- `scripts/project_publish.py`
- `scripts/finish_task.py`

A future file may be added only with regression coverage and the same pre-mutation exact-byte proof.

## Why recopy is safe here

In `harness_mode=platform`, Dev Platform owns the lifecycle files being overwritten. Recopy remains gated by exact target equivalence for every conflict and by configuration-contract verification after render. It does not grant permission to overwrite arbitrary product files or diverged platform files.

## Failure behavior

- mixed target-equivalent and real conflicts: fail closed;
- target file differs before update: fail closed;
- recopy leaves rejects: fail closed;
- bootstrap or validation fails: fail closed;
- project configuration contract changes beyond allowed release metadata: fail closed;
- no branch is pushed and no PR is opened on any failure.
