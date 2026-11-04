## ADDED Requirements

### Requirement: Composition finalization archives through the shared finalize function

Composition finalization SHALL archive each child in manifest order through the same finalize function as the queue finalize job, with the composition's review evidence, and SHALL report the unmet preconditions of every child before archiving any child.

#### Scenario: Two children miss preconditions
- **WHEN** composition finalization starts and two children each miss a precondition
- **THEN** one error names both children and their problems and no child is archived
