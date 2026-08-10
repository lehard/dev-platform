## ADDED Requirements

### Requirement: Historical Copier replay may recover only proven reclaimed platform files

Managed rollout MAY use guarded Copier recopy to recover a smart-update conflict on a platform-owned harness only when every conflicted path is explicitly classified as reclaimed platform ownership and the downstream file already matched the exact target immutable template before the smart update began. The recovery SHALL remain fail-closed for any unallowlisted or currently divergent path.

#### Scenario: Platform-owned file already equals target but historical replay conflicts
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** `scripts/project_publish.py` exactly matches the target immutable platform template before update
- **WHEN** `copier update` replays historical downstream edits and emits `scripts/project_publish.py.rej`
- **THEN** managed rollout may reset the ephemeral rollout branch and use guarded recopy
- **AND** it verifies protected snapshots and platform configuration after recopy
- **AND** it can continue to normal validation and reviewed PR creation

#### Scenario: Reclaimed path still contains downstream divergence
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** an allowlisted reclaimed path does not match the target immutable template before update
- **WHEN** Copier reports a conflict on that path
- **THEN** managed rollout fails closed
- **AND** it does not use recopy, push a rollout branch, or open a PR

#### Scenario: Platform-mode conflict is unrelated to reclaimed ownership
- **GIVEN** a managed repository uses `harness_mode=platform`
- **WHEN** Copier reports any conflict outside the proven reclaimed set
- **THEN** managed rollout fails closed without recopy
