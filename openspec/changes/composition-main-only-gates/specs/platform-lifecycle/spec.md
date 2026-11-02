## MODIFIED Requirements

### Requirement: Shared candidates grow append-only and are draft until complete

A shared Requirement candidate manifest SHALL list the expected mandatory changes and the reviewed child contributions integrated so far.

#### Scenario: Later child is appended

- **GIVEN** a draft candidate PR exists for the first verified child
- **WHEN** the next child is ready
- **THEN** its exact delta is added as new commits on the same branch and the manifest is extended
- **AND** the same PR is updated by fast-forward push without a force push or duplicate

#### Scenario: Divergent or reordered growth is refused

- **GIVEN** an existing candidate branch
- **WHEN** a revision changes, removes or reorders an earlier child, a child head changed, or the branch is not a fast-forward
- **THEN** publication stops before any push or PR mutation naming the exact boundary

#### Scenario: Interrupted run resumes

- **GIVEN** a draft or ready candidate PR already exists for the exact branch
- **WHEN** the supervisor is rerun
- **THEN** it resumes that branch and PR without creating another PR or candidate

#### Scenario: Completion applies the final gates

- **GIVEN** every mandatory child is present
- **WHEN** the candidate is made ready
- **THEN** full checks are valid for the exact final head under the composition gate rules and required CI passes on that head before the protected merge path runs
- **AND** the Requirement retrospective checkpoint is not a ready or merge precondition

### Requirement: A shared candidate leaves draft only when complete and finalized

Ready, merge arming and queue admission SHALL require a complete manifest, composition-level review of cross-child properties, a single finalization of all children and full checks valid on the final head, allowing proven main-only gate carry. Required CI SHALL pass on the exact head before ready. These pre-merge steps SHALL NOT require the Requirement retrospective. Terminal reconciliation SHALL require the same final gates and the retrospective checkpoint.

#### Scenario: A candidate is marked ready

- **WHEN** the shared candidate PR is marked ready, armed for merge or admitted to the publication queue
- **THEN** a complete manifest, composition-level review of cross-child properties, a single finalization of all children and valid final-head full checks are required
- **AND** required CI has passed on the exact head
- **AND** the Requirement retrospective checkpoint is not required for these pre-merge steps

#### Scenario: Terminal close requires the retrospective

- **WHEN** terminal reconciliation closes the Requirement after delivery
- **THEN** the final composition gates and Requirement retrospective checkpoint remain mandatory
- **AND** a missing or stale checkpoint prevents terminal close

## ADDED Requirements

### Requirement: A composition keeps its gates across a proven main-only update

A composition SHALL reuse review, finalization and full checks on a new head only when the existing main-only proof binds trusted passed-gate evidence to that head. Proof-bound full-check evidence SHALL remain valid without a new run despite its original evidence head. Required CI SHALL pass on the exact new head before ready or admission.

#### Scenario: Unrelated merge into main

- **GIVEN** a finalized composition with trusted passed gates and full checks
- **WHEN** its head absorbs main and the existing main-only proof holds
- **THEN** review, finalization and full checks remain valid without a rerun
- **AND** the carried evidence preserves its original check head and records its proof binding to the new head

#### Scenario: Proof does not hold

- **WHEN** the new head changes own content outside a proven main-only integration
- **THEN** the gates are not reused and the existing repair and full-review rules apply

#### Scenario: Trusted full-check evidence is missing

- **WHEN** the old gated head or passed full-check evidence cannot be proven
- **THEN** reuse is refused with a reason and no new successful check run is claimed

#### Scenario: Required CI does not prove the new head

- **WHEN** required CI is pending, failed, unavailable or passed only on another head
- **THEN** the composition is not made ready or admitted

### Requirement: Integration repair re-checks a composition exactly once

After genuine composition integration repair, the repair path SHALL complete final publication once: unchanged own content gets one full-check pass and admission; changed own content gets full composition review, finalization and one full-check pass before admission. No manual advance or conflict-only review SHALL be used. Proven main-only integration SHALL retain the existing gate-carry rule.

#### Scenario: Repair keeps the identity

- **WHEN** genuine integration repair finishes without changing composition own-content identity
- **THEN** final publication runs full checks once and admits the composition without advance

#### Scenario: Repair changes the identity

- **WHEN** integration repair changes composition own content
- **THEN** a full composition review is offered
- **AND** finalization, one full-check pass and admission follow automatically after review

#### Scenario: Repair result only integrates main

- **WHEN** the repair result satisfies the accepted main-only proof
- **THEN** it keeps the proven gate-carry behavior and still waits for exact-head required CI before ready
