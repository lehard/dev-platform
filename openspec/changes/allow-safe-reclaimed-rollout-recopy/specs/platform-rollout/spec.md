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

### Requirement: Managed rollout failures remain fail-closed and diagnosable

The managed rollout workflow SHALL preserve a non-zero rollout preparation result and SHALL surface its blocking reason in GitHub Actions when preparation fails. A failed checked subprocess SHALL be reported with its exact last emitted command marker and the preparation exit code when no stable platform blocker marker exists. Diagnostic handling SHALL NOT push the rollout branch, open a pull request, skip a guard, or convert a failed rollout into success.

#### Scenario: Prepare fails on a safety guard
- **WHEN** `rollout_project.py` exits non-zero because a managed safety invariant fails
- **THEN** the workflow records the command output
- **AND** emits a readable GitHub Actions error annotation containing the final `Managed rollout: BLOCKED:` reason
- **AND** remains failed
- **AND** branch push and PR creation remain skipped

#### Scenario: Downstream validation command fails
- **GIVEN** rollout safely reached downstream platform/product validation
- **WHEN** a checked subprocess exits non-zero without a `Managed rollout: BLOCKED:` marker
- **THEN** the workflow identifies the final command line emitted as `+ <command>` and reports that command with the exit code
- **AND** arbitrary source-code lines containing words such as `Error:` SHALL NOT replace that blocker
- **AND** the failed command remains a blocking result rather than becoming recoverable

### Requirement: Rollout service branches do not weaken interactive task branch rules

Managed rollout SHALL use only the reserved service-branch form `dev-platform/rollout-vX.Y.Z` generated from an exact SemVer release. This automation branch SHALL be validated through rollout-specific validation and SHALL NOT cause interactive task lifecycle rules to accept arbitrary `dev-platform/*` branches in place of `agent/<task>`.

#### Scenario: Rollout validates an automation branch
- **GIVEN** managed rollout created `dev-platform/rollout-v1.2.3`
- **WHEN** downstream validation runs before push
- **THEN** rollout-specific platform validation and selected project checks MAY run on that service branch
- **AND** no interactive `agent/<task>` branch precondition is required
- **AND** ordinary task creation/publication continues to use its existing agent branch contract
