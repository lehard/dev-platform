## MODIFIED Requirements

### Requirement: Expensive validation requires a fresh task base

For platform-owned task execution, the lifecycle SHALL refresh its observation of the configured remote integration branch and verify that the current task head is based on the authoritative remote history before running expensive full/protected validation intended as delivery evidence.

One bounded exception SHALL exist, for trusted coordinator finalization of a reviewed candidate. Selected-check execution SHALL accept an explicit proven base, and with it SHALL require that the head forks from exactly that commit on the remote integration branch's history, instead of requiring the head to contain the current remote integration branch. The proven base SHALL be accepted only for executed checks in the coordinator lifecycle mode. It SHALL be refused, before any command starts and with an error naming the violated condition, when combined with evidence output, a contribution base or protected-full validation, or when it is not the merge base of the head and the remote integration branch. A second bounded exception SHALL exist for a coordinator-managed candidate, whose integration the publication queue performs by merging the current integration branch and gating on required checks of the integrated head. Its developer evidence-producing validation, handoff, re-admission and status SHALL accept a head that does not contain the current remote integration branch when a trial merge of the head with the observed integration head is clean, or conflicts only in files that the project declares as generated in the committed check configuration of that observed integration commit; a path changed on both sides is not by itself a reason to block. The lifecycle SHALL report that behind-mergeable contract with the observed integration head, the merge base, the paths changed on both sides and the generated-file conflicts, and record it in the evidence. The declaration SHALL be read only from the observed integration commit, never from the candidate; a malformed declaration SHALL fail explicitly, and a project without a declaration has no generated files. A conflict in any other file or a missing merge base SHALL block before any expensive command, naming the conflicting files and the reconcile command. Evidence recorded earlier under the behind-disjoint contract SHALL remain valid. Outside these two exceptions, developer preflight, evidence-producing validation and protected CI SHALL keep the fresh-base requirement unchanged.

#### Scenario: Task remains fresh before full validation

- **GIVEN** the current task head contains the freshly fetched `origin/<main>` in its ancestry
- **WHEN** full/protected validation is about to begin
- **THEN** the lifecycle continues with the existing selected validation commands
- **AND** no additional human action is required solely for freshness

#### Scenario: Remote main advances during task execution

- **GIVEN** the task began from an earlier integration state
- **AND** `origin/<main>` has advanced so the current task head no longer contains that authoritative history
- **WHEN** expensive full/protected validation is requested
- **THEN** the lifecycle stops before executing that expensive validation set
- **AND** reports a resumable rebase/reconciliation-first outcome with the observed relationship
- **AND** does not automatically reset, force-rebase, or force-push the task branch

#### Scenario: Freshness cannot be established

- **WHEN** the remote integration state required for authoritative freshness cannot be observed
- **THEN** the lifecycle does not claim the task is fresh for delivery-evidence validation
- **AND** returns an explicit safe blocker/retry outcome rather than silently proceeding

#### Scenario: Task is reconciled and retried

- **GIVEN** a stale task has been safely reconciled onto the current authoritative integration history
- **WHEN** the freshness check is repeated
- **THEN** it succeeds if ancestry is now valid
- **AND** the ordinary validation lifecycle resumes without a second special workflow

#### Scenario: Coordinator finalization checks the reviewed content on its proven base

- **GIVEN** a coordinator-mode finalization checkout of a reviewed candidate whose head forks from its proven base
- **AND** `origin/<main>` has advanced past that base
- **WHEN** selected checks are executed with that proven base
- **THEN** the freshness gate passes, naming the coordinator-finalization contract and the base
- **AND** the selected commands actually run and a failing command fails the invocation

#### Scenario: Proven base is not a general freshness bypass

- **WHEN** a proven base is passed together with evidence output, a contribution base or protected-full validation, without execution, outside the coordinator lifecycle mode, or with a commit that is not the merge base of the head and `origin/<main>`
- **THEN** the invocation fails before any command starts, naming the violated condition
- **AND** an invocation without a proven base on a stale head is still blocked by the fresh-base requirement

#### Scenario: Coordinator candidate behind main overlapping only in the generated manifest is handed off

- **GIVEN** a coordinator-managed candidate whose head does not contain the freshly fetched `origin/<main>`
- **AND** both the candidate and `origin/<main>` changed the declared generated platform manifest, and a trial merge conflicts only there
- **WHEN** evidence-producing selected checks, the developer handoff, re-admission or status run
- **THEN** the freshness gate passes, naming the behind-mergeable contract, the observed main, the merge base and the generated-file conflict
- **AND** the evidence records that contract
- **AND** no reconcile is required

#### Scenario: Coordinator candidate behind a disjoint main is handed off without reconcile

- **GIVEN** a coordinator-managed candidate whose head does not contain the freshly fetched `origin/<main>`
- **AND** the files `origin/<main>` changed since the merge base are disjoint from the candidate's changed files and a trial merge is clean
- **WHEN** evidence-producing selected checks or the developer handoff run
- **THEN** the freshness gate passes under the behind-mergeable contract, naming the observed main and the merge base
- **AND** the evidence records that contract
- **AND** no reconcile is required

#### Scenario: Coordinator candidate overlapping main with a clean merge is handed off

- **GIVEN** a coordinator-managed candidate whose head does not contain `origin/<main>`
- **AND** `origin/<main>` changed an ordinary file the candidate also changed, and a trial merge is clean
- **WHEN** evidence-producing selected checks or the developer handoff run
- **THEN** the freshness gate passes under the behind-mergeable contract, naming the overlapping path
- **AND** no reconcile is required

#### Scenario: Coordinator candidate overlapping main must reconcile

- **GIVEN** a coordinator-managed candidate whose head does not contain `origin/<main>`
- **AND** both changed a file that is not declared generated and a trial merge conflicts in it
- **WHEN** evidence-producing selected checks or the developer handoff run
- **THEN** the lifecycle stops before any expensive command, naming the conflicting files and the reconcile command

#### Scenario: A candidate cannot declare its own conflict generated

- **GIVEN** a coordinator-managed candidate that adds a generated-file declaration for a file it conflicts in
- **AND** the observed `origin/<main>` does not declare that file
- **WHEN** evidence-producing selected checks or the developer handoff run
- **THEN** the conflict blocks as a real conflict

#### Scenario: Non-coordinator task keeps the fresh-base rule

- **GIVEN** a task published without the coordinator queue whose head does not contain `origin/<main>`
- **WHEN** evidence-producing validation is requested
- **THEN** it is blocked by the fresh-base requirement even when the changed files are disjoint

### Requirement: Freshness drift is visible before another expensive validation run

Supported task status/preflight SHALL expose when the current managed task head is behind authoritative main before the platform begins a new expensive authoritative validation cycle. For a coordinator-managed candidate whose head is behind main under the behind-mergeable contract, status SHALL report that state as not requiring reconciliation. A stale observation SHALL remain resumable rather than being reported as terminal task failure.

#### Scenario: Main advanced after prior task work

- **GIVEN** a managed task was previously valid
- **AND** authoritative main advances while the task remains active
- **WHEN** the operator asks for task status or begins the finish path
- **THEN** the platform reports that reconciliation is required before expensive validation
- **AND** points to the supported reconcile operation

#### Scenario: Coordinator candidate behind a disjoint main

- **GIVEN** a coordinator-managed candidate whose head is behind `origin/<main>` and a trial merge is clean or conflicts only in declared generated files
- **WHEN** the operator asks for task status
- **THEN** status reports the behind-mergeable state and that no reconciliation is required
