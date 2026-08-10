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

The managed rollout workflow SHALL preserve a non-zero rollout preparation result and SHALL surface its blocking reason in GitHub Actions when preparation fails. The selected-check helper SHALL emit a reserved command marker before each selected downstream command so compiler, diff, or application output cannot be mistaken for the command being executed. Diagnostic handling SHALL NOT push the rollout branch, open a pull request, skip a guard, or convert a failed rollout into success.

#### Scenario: Prepare fails on a safety guard
- **WHEN** `rollout_project.py` exits non-zero because a managed safety invariant fails
- **THEN** the workflow records the command output
- **AND** emits a readable GitHub Actions error annotation containing the final `Managed rollout: BLOCKED:` reason
- **AND** remains failed
- **AND** branch push and PR creation remain skipped

#### Scenario: Downstream validation command fails
- **GIVEN** rollout safely reached downstream platform/product validation
- **WHEN** a checked selected command exits non-zero without a `Managed rollout: BLOCKED:` marker
- **THEN** `select_checks.py` has emitted `DEV_PLATFORM_CHECK_COMMAND: <command>` immediately before that command
- **AND** the workflow reports the last such reserved marker with the exit code
- **AND** arbitrary source/compiler lines beginning with `+` or containing `Error:` SHALL NOT replace that blocker
- **AND** the failed command remains a blocking result rather than becoming recoverable

#### Scenario: Failure occurs outside selected checks
- **WHEN** rollout preparation exits non-zero before any stable blocker or selected-check marker exists
- **THEN** the workflow reports the preparation exit code generically
- **AND** does not guess a command from arbitrary subprocess output
- **AND** the rollout remains failed

### Requirement: Managed rollout emits one machine-readable terminal diagnostic

For every failed managed-project rollout attempt, the workflow SHALL emit one canonical machine-readable diagnostic envelope derived from structured rollout state. The envelope SHALL be available without requiring arbitrary full-log scraping and SHALL NOT alter rollout safety or outcome.

The envelope SHALL include at least: schema version, terminal status, target project, target immutable release, failure stage, failure category, stable reason, exit code, selected command when known, same-input retry advisory, and structured evidence already known to rollout such as conflict paths. It SHALL exclude credentials, unrestricted environment dumps, tokens, and raw logs.

#### Scenario: Safety guard blocks rollout
- **WHEN** a managed safety invariant fails deterministically
- **THEN** the diagnostic category is `safety_guard` or another more specific stable safety category
- **AND** the stage identifies where the guard failed
- **AND** the reason contains the canonical managed-rollout blocker
- **AND** `retry_same_inputs` is `pointless` unless the platform can prove the failure may be transient
- **AND** the workflow remains failed

#### Scenario: Selected downstream check fails
- **GIVEN** rollout has emitted `DEV_PLATFORM_CHECK_COMMAND: <command>`
- **WHEN** that selected command exits non-zero
- **THEN** the diagnostic stage is `downstream_check`
- **AND** the command field contains exactly the reserved selected command
- **AND** arbitrary compiler, diff, or application output SHALL NOT replace the command
- **AND** the exit code is preserved

#### Scenario: Runtime/environment mismatch is known
- **WHEN** rollout can identify that a platform-owned runtime baseline differs from the required managed validation baseline
- **THEN** the diagnostic category is `runtime_environment`
- **AND** the reason identifies the required/observed baseline without exposing secrets
- **AND** a same-input retry SHALL NOT be labeled `safe` when no environment input can change between attempts

#### Scenario: Failure is not classifiable
- **WHEN** rollout fails without a known blocker, structured conflict, or selected-check marker
- **THEN** the diagnostic category is `unknown`
- **AND** the stage is the narrowest known stage or `unknown`
- **AND** `retry_same_inputs` is `unknown`
- **AND** the workflow does not infer a cause from arbitrary log text

#### Scenario: Diagnostic is published for agents and humans
- **WHEN** a rollout attempt reaches a terminal failed state
- **THEN** the canonical diagnostic JSON is written to a predictable path such as `rollout-diagnostic.json`
- **AND** a compact rendering is appended to the GitHub Actions step summary
- **AND** the workflow attempts to upload a predictably named diagnostic artifact
- **AND** the annotation, summary, and artifact represent the same canonical terminal failure

#### Scenario: Diagnostic artifact upload fails
- **GIVEN** the original rollout is already failed
- **WHEN** diagnostic artifact upload or summary presentation fails
- **THEN** that presentation failure SHALL NOT replace the original blocker
- **AND** SHALL NOT convert the rollout to success
- **AND** the workflow SHALL preserve the original non-zero result

#### Scenario: Consumer reads a future diagnostic schema
- **GIVEN** a consumer understands schema version 1
- **WHEN** later platform versions add optional diagnostic fields
- **THEN** the existing stable fields remain interpretable
- **AND** consumers can reject or explicitly handle an unsupported schema version rather than relying on exact JSON byte shape

### Requirement: Managed rollout validates with the platform CI runtime baseline

Managed rollout SHALL provision the same platform-owned base runtime versions used by the generated downstream Dev Platform gate before executing selected downstream checks. Runtime parity SHALL be tested so a platform release cannot silently validate a consumer under a different Node baseline than the generated PR gate.

#### Scenario: Rollout executes JavaScript checks
- **GIVEN** the generated Dev Platform workflow pins Node `20.19.0`
- **WHEN** managed rollout reaches selected downstream checks
- **THEN** the rollout job has provisioned Node `20.19.0` before those checks
- **AND** the downstream build is evaluated under the same platform-owned Node baseline as its PR gate

#### Scenario: Platform changes the generated Node baseline
- **WHEN** a later platform release changes the Node version in the generated Dev Platform workflow
- **THEN** validation fails unless managed rollout is updated to the same version in that release

### Requirement: Rollout service branches do not weaken interactive task branch rules

Managed rollout SHALL use only the reserved service-branch form `dev-platform/rollout-vX.Y.Z` generated from an exact SemVer release. This automation branch SHALL be validated through rollout-specific validation and SHALL NOT cause interactive task lifecycle rules to accept arbitrary `dev-platform/*` branches in place of `agent/<task>`.

#### Scenario: Rollout validates an automation branch
- **GIVEN** managed rollout created `dev-platform/rollout-v1.2.3`
- **WHEN** downstream validation runs before push
- **THEN** rollout-specific platform validation and selected project checks MAY run on that service branch
- **AND** no interactive `agent/<task>` branch precondition is required
- **AND** ordinary task creation/publication continues to use its existing agent branch contract
