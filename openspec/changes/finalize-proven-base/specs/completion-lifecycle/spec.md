## MODIFIED Requirements

### Requirement: Gate evidence is reused for unchanged task content

Required-check, selected-check and review evidence SHALL be bound to the task-content identity it verified and SHALL be reused by later lifecycle steps when that identity is unchanged; changed or unprovable identity SHALL require the gate again. A clean merge of `main`, a `main` advance, lifecycle archiving and a coordinator update SHALL NOT by themselves invalidate a passed independent review. When a developer re-admits a descendant head in place of an admitted head through queue supersession, the new review-pending record SHALL keep every recorded gate that is still provably bound to the new task-content identity, except required checks and the gates the new handoff supplies. A kept passed review SHALL complete the review job without launching a reviewer. Re-admission SHALL NOT carry a failed review, and SHALL NOT relax any refusal of re-admission over finding-level escalations or material findings.

#### Scenario: Bookkeeping commit after review
- **WHEN** only lifecycle evidence paths change
- **THEN** review and check evidence remain valid

#### Scenario: Clean main merge re-admitted with unchanged task content
- **GIVEN** a candidate whose independent review passed and which waits in a re-admissible state
- **WHEN** the developer merges the advanced `main` cleanly, with no task-path overlap, and re-admits the new head in the same PR
- **THEN** the review-pending record keeps the passed review rebound to the new identity
- **AND** the review job completes from the kept review without launching a reviewer

#### Scenario: Substantive conflict fix
- **WHEN** a re-admitted head or an integration repair changes task content, for example by resolving a conflict in a task path
- **THEN** the passed review is not kept and a new independent review runs for the new identity

### Requirement: Finalization follows review and repair

A coordinator-managed candidate SHALL be archived by a finalize job only after required checks and Independent Review pass for its current task-content identity, using that reused evidence. Finalization SHALL NOT change task-content identity; a later task-content change SHALL return the candidate to review and finalization. When selected checks must be re-established during finalization, the finalize job SHALL run the real selected checks against the proven base of the reviewed task content. That base is the task-content base of the identity proven equivalent to the candidate's recorded identity, and the checks SHALL use the bounded coordinator-finalization freshness contract rather than require the head to contain current `main`. The harness-executed evidence SHALL record that contract and base. Finalization SHALL NOT fetch or merge `main`, and its only push SHALL be a fast-forward of the claimed head with the archive move. A failing selected check SHALL still escalate the candidate, and an unbound semantic-verification receipt SHALL still require the developer's handoff.

#### Scenario: Review passes
- **WHEN** review and checks pass for the candidate identity
- **THEN** finalize archives the change and the candidate becomes ready

#### Scenario: Main advances between review repair and finalize
- **GIVEN** a candidate whose task content changed in a review repair and whose selected-checks gate is therefore not reusable
- **AND** other PRs advanced `main` after the review
- **WHEN** the finalize job re-establishes selected checks
- **THEN** the real selected checks run against the proven base of the reviewed content
- **AND** the candidate is not blocked because its head does not contain current `main`

#### Scenario: Re-established check fails
- **WHEN** a selected check fails under the proven-base contract
- **THEN** finalization does not archive and the candidate is escalated naming the failure

#### Scenario: Finalization does not actualize the base
- **GIVEN** `main` advanced after review
- **WHEN** finalization archives the candidate
- **THEN** any pushed finalization commit has the claimed head as its only parent and contains no merge of `main`
