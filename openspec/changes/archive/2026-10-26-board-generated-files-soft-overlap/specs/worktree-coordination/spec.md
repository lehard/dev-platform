## MODIFIED Requirements

### Requirement: Hard and soft overlap are classified deterministically

The coordination mechanism SHALL distinguish a hard overlap from a soft or potential overlap using normalized repository-relative scope evidence. Except for a declared generated path, an exact concrete file path present in the current task's claim and another active task's concrete claimed or factual scope SHALL be a hard overlap. A shared directory, subsystem, broad glob, or other non-concrete proximity SHALL remain advisory by itself. A path the project declares generated in the committed check configuration at the observed remote integration branch SHALL NOT be a hard overlap and SHALL remain reported as a soft overlap; a declaration present only on a task branch SHALL NOT change the classification, and an unreadable declaration SHALL stop the scope gate instead of being treated as empty.

When an active task has factual changed-file scope, that concrete evidence SHALL take precedence over a broader declared scope for determining hard overlap; the broader declaration MAY still contribute a warning.

#### Scenario: Active task already changes the same file

- **GIVEN** active task A factually changes `template/scripts/_platform_common.py`
- **AND** task B claims that same concrete file
- **WHEN** task B runs admission
- **THEN** task B receives `WAIT`
- **AND** the diagnostic identifies task A and the conflicting repository-relative path

#### Scenario: Only a broad subsystem overlaps

- **GIVEN** task A and task B both mention the same directory, subsystem, or broad glob
- **AND** no exact concrete file conflict is established
- **WHEN** admission runs
- **THEN** the overlap is reported as soft or potential
- **AND** that overlap alone does not force `WAIT`

#### Scenario: Factual scope disproves a broad declared conflict

- **GIVEN** an active task declared a broad scope
- **AND** its available factual changed-file scope contains no concrete path claimed by the current task
- **WHEN** admission classifies the overlap
- **THEN** the broad declaration does not become a hard blocker by itself

#### Scenario: Tasks share only a declared generated file

- **GIVEN** active task A and task B both change `template/dev-platform/platform-manifest.json`
- **AND** that path is declared generated at the observed `origin/<main>`
- **WHEN** task B runs admission or a scope-gate recheck
- **THEN** no hard overlap is reported for that path
- **AND** the advisory warning still lists it

#### Scenario: A task cannot declare its own shared file generated

- **GIVEN** task B adds a generated-file declaration for a file active task A also changes
- **AND** the declaration is absent at the observed `origin/<main>`
- **WHEN** task B runs a scope-gate recheck
- **THEN** the shared file remains a hard overlap
