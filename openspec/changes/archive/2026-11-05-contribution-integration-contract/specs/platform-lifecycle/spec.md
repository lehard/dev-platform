## ADDED Requirements

### Requirement: Contribution freshness is measured against its target branch

Task status, finish, reconcile, handoff and selected-check freshness of an open contribution SHALL use its recorded requirement branch instead of main. A head behind a target that merges cleanly is behind-mergeable; a conflict requires reconcile. Reconcile SHALL merge the target and move the contribution base to the merged target head. Main-target tasks keep the main rule.

#### Scenario: Main moved, requirement branch did not
- **WHEN** main advanced and the contribution contains its current target
- **THEN** status reports it fresh and names the target branch

#### Scenario: Requirement branch moved with a conflict
- **WHEN** the head conflicts with its target
- **THEN** status requires reconcile naming the target and the conflicting paths

#### Scenario: Contribution is reconciled
- **WHEN** reconcile merges the target
- **THEN** the contribution base is the merged target head and later review sees only the child's own content

#### Scenario: Target cannot be observed
- **WHEN** the recorded target branch cannot be read
- **THEN** freshness refuses naming the branch and is not reported fresh

### Requirement: A requirement branch absorbs main through a supported command

`execute_requirement.py absorb-main --requirement <ref>` SHALL merge current main into the requirement branch and push it by fast-forward from the exact observed head. It SHALL refuse a queue-owned composition, a missing branch, a moved head or a conflict, naming the reason and next action, and SHALL change no contribution identity.

#### Scenario: Clean merge
- **WHEN** main merges cleanly into an unowned requirement branch
- **THEN** the branch gains the merge, the manifest is unchanged, and open contributions keep their base

#### Scenario: Merge conflicts
- **WHEN** main conflicts with the requirement branch
- **THEN** nothing is pushed and the refusal names the paths and the composition repair as the next action

#### Scenario: Composition is queue-owned
- **WHEN** the queue owns the composition
- **THEN** the command refuses naming the queue state

### Requirement: A contribution uses its proven base and a main-target candidate its merge base

Selected checks of a contribution SHALL run under the contribution-base contract, scoped to that base, which the head and the target SHALL contain. An unproven contribution base SHALL be refused. The proven-base merge-base rule with `origin/<main>` SHALL apply only to main-target candidates.

#### Scenario: Contribution finalization after main was absorbed
- **WHEN** a contribution finalizes after its target absorbed main
- **THEN** its selected checks cover only the diff from its contribution base

#### Scenario: Main-target candidate
- **WHEN** a main-target candidate finalizes
- **THEN** its proven base is still required to be the merge base with `origin/<main>`
