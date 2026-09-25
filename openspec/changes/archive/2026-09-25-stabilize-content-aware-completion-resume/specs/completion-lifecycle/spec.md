## ADDED Requirements

### Requirement: Completion evidence freshness follows proven task-content identity

Managed completion evidence SHALL NOT become stale solely because HEAD changed through a platform-owned lifecycle transition when the platform can mechanically prove that the validated task-owned content is unchanged. Evidence SHALL retain its original commit provenance, and reuse SHALL require a deterministic auditable content-equivalence proof.

If task-owned content changed or equivalence cannot be proven, the relevant evidence SHALL be treated as stale and the required validation or retrospective SHALL run again.

#### Scenario: Archive commit changes HEAD but not task content

- **GIVEN** a managed task has fresh retrospective or automated-check evidence for its completed task content
- **AND** the normal archive lifecycle creates a bookkeeping/spec-fold commit without changing that validated task content
- **WHEN** terminal completion evaluates evidence freshness
- **THEN** the platform MAY accept the evidence if content equivalence is mechanically proven
- **AND** does not require a duplicate review solely because the commit SHA changed.

#### Scenario: Task content changes after validation

- **GIVEN** managed completion evidence exists for an earlier task-content identity
- **WHEN** implementation or other task-owned content changes afterward
- **THEN** the prior evidence is stale
- **AND** completion requires the relevant fresh validation or retrospective before publication.

#### Scenario: Reconciliation changes the base ambiguously

- **GIVEN** origin/base advances after validation
- **AND** the platform cannot prove the new base is irrelevant to the validated task content
- **WHEN** completion reconciles the task
- **THEN** evidence reuse is refused
- **AND** the task follows the required revalidation path.

### Requirement: Armed exact-head publication resumes through status before republishing

After the platform has proven an existing PR for the exact task head and a durable auto-merge/remote merge intent, a subsequent completion invocation SHALL first observe and reconcile that existing publication state. It SHALL NOT rerun first-publication push/create logic or expensive validation solely because the prior bounded local wait ended before GitHub reported `MERGED`.

#### Scenario: Auto-merge is armed but merge is still pending

- **GIVEN** an exact-head PR exists and auto-merge intent is durably verified
- **AND** required checks or GitHub merge processing are still pending
- **WHEN** local bounded waiting ends or completion is invoked again
- **THEN** the platform reports a resumable nonterminal state with an actionable status path
- **AND** does not repeat full validation or republish the same head solely because merge is not yet terminal.

#### Scenario: Existing remote intent materially changed

- **GIVEN** a prior publication state exists
- **BUT** the observed PR head, required-check state, merge intent or base relationship no longer matches the proven resumable state
- **WHEN** completion resumes
- **THEN** the cheap resume path fails closed
- **AND** routes to explicit reconciliation/revalidation appropriate to the observed change.

### Requirement: Expected nonterminal publication states are bounded diagnostics

Expected resumable states in the protected-main completion flow SHALL be surfaced as structured actionable outcomes rather than uncaught Python subprocess tracebacks. This classification SHALL NOT convert an actual publication failure into success.

#### Scenario: Project publish reports accepted auto-merge without terminal merge

- **GIVEN** GitHub accepted the exact-head auto-merge intent
- **BUT** the local bounded wait ended before the PR reached `MERGED`
- **WHEN** the finish wrapper receives that nonterminal outcome
- **THEN** it reports the existing PR/status and next action without a raw traceback
- **AND** preserves nonterminal state so the caller does not mistake it for completed delivery.
