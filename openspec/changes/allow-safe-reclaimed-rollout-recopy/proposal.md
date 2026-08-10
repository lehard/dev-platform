# Change: Allow safe recopy for already-reclaimed platform files

## Why

The v1.4.13 managed rollout exposed a second-order Copier migration problem in Cuby. Cuby had temporarily carried a downstream `scripts/project_publish.py` override for a bug that is now fixed upstream. After Cuby was reconciled to the exact v1.4.13 template bytes, `copier update` still replayed the historical downstream diff and emitted `scripts/project_publish.py.rej`.

The current rollout recovery path allows guarded recopy only for `harness_mode=project`, so a platform-owned repository can remain permanently blocked even when the conflicted file already exactly matches the target immutable template. This is unnecessary friction but must not be solved by broad conflict suppression.

## What changes

- Extend the narrowly allowlisted reclaimed-platform set to `scripts/project_publish.py`.
- Permit guarded recopy for `harness_mode=platform` only when every conflict is on an explicitly reclaimed platform path that already matched the exact target template before the smart update.
- Continue to fail closed for any platform-mode conflict involving an unallowlisted or downstream-divergent file.
- Preserve project-owned snapshots and platform config invariants around the recopy.
- Add regression coverage reproducing the Cuby v1.4.13 historical-diff conflict.

## Scope

This affects existing-project managed updates only. Fresh project rendering is unchanged. The change is universal rollout behavior; it does not add Cuby-specific logic beyond the generic reclaimed-path allowlist entry justified by the upstream ownership transition.

## Success criteria

A platform-owned managed repository whose current `scripts/project_publish.py` already equals the target immutable template can recover from a historical Copier replay conflict through guarded recopy. Any real downstream divergence or unrelated conflict still blocks before push/PR creation.
