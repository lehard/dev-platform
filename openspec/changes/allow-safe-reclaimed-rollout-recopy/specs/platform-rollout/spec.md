## ADDED Requirements

### Requirement: Historical Copier replay may recover only proven platform-owned state

Managed rollout MAY use guarded Copier recopy to recover a smart-update conflict on a platform-owned harness only when every conflicted path is proven safe from immutable pre-update state. A conflict is safe when either (a) an explicitly reclaimed migration path already matches the exact target immutable template, or (b) the committed downstream path exactly matches the same path in the immutable platform template version recorded by `.copier-answers.yml`. Missing/missing SHALL count as baseline equivalence. Any currently divergent or otherwise unproven path SHALL remain fail-closed.

#### Scenario: Platform-owned file already equals target but historical replay conflicts
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** `scripts/project_publish.py` exactly matches the target immutable platform template before update
- **WHEN** `copier update` replays historical downstream edits and emits `scripts/project_publish.py.rej`
- **THEN** managed rollout may reset the ephemeral rollout branch and use guarded recopy
- **AND** it verifies protected snapshots and platform configuration after recopy
- **AND** it can continue to normal validation and reviewed PR creation

#### Scenario: Unmodified old-platform file conflicts during historical replay
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** a conflicted downstream path in committed `HEAD` exactly equals the same path in the immutable platform version recorded by `.copier-answers.yml`
- **WHEN** smart Copier update emits a rejection for that path
- **THEN** the path is eligible for guarded recopy without adding a repository-specific allowlist entry
- **AND** after recopy the path SHALL match the new target template state

#### Scenario: Path is absent in both downstream and recorded old template
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** a rejection names a path absent from both committed downstream `HEAD` and the recorded old consumer template
- **THEN** that missing/missing state is treated as baseline-equivalent
- **AND** guarded recopy MAY recover it if every other conflict is also proven safe

#### Scenario: Reclaimed path still contains downstream divergence
- **GIVEN** a managed repository uses `harness_mode=platform`
- **AND** an allowlisted reclaimed path does not match the target immutable template before update
- **AND** it also does not match its recorded old-template state
- **WHEN** Copier reports a conflict on that path
- **THEN** managed rollout fails closed
- **AND** it does not use recopy, push a rollout branch, or open a PR

#### Scenario: Platform-mode conflict contains real downstream customization
- **GIVEN** a managed repository uses `harness_mode=platform`
- **WHEN** any conflicted path differs from both its recorded old-template state and any applicable reclaimed target state
- **THEN** managed rollout fails closed without recopy

#### Scenario: Baseline proof is computed after Copier mutates the worktree
- **WHEN** rollout classifies conflicts after smart update has emitted `.rej` files
- **THEN** downstream equivalence SHALL be derived from committed `HEAD` rather than current worktree bytes
- **AND** the old side SHALL be read from the exact immutable tag recorded by `.copier-answers.yml`
