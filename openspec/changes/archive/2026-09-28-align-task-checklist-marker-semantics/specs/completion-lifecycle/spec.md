# completion-lifecycle Specification Delta

## ADDED Requirements

### Requirement: Task checklist counting matches upstream OpenSpec markers

Every platform gate that decides whether a change's tasks are complete (lifecycle readiness and archive, completed-change hygiene, managed delivery provenance and shared Requirement integration) SHALL count tasks.md checklist items using the same task-line semantics as upstream OpenSpec apply progress: an item with a `-`, `*`, `+`, `N.` or `N)` list marker followed by a checkbox is a task, and a task is complete only when its checkbox content is `x` or `X`. Any other checkbox content SHALL count as incomplete.

#### Scenario: Alternative list markers keep a change incomplete

- **GIVEN** an active change whose only unchecked tasks are written as `+ [ ] task`, `1. [ ] task` or `1) [ ] task`
- **WHEN** lifecycle readiness or completed-change hygiene is evaluated
- **THEN** the change is reported as having incomplete tasks

#### Scenario: Unknown checkbox content is incomplete

- **GIVEN** an active change whose only open task is `- [~] partial`
- **WHEN** lifecycle readiness or completed-change hygiene is evaluated
- **THEN** the task counts as incomplete and the change is not treated as complete

#### Scenario: Standard checkboxes keep their meaning

- **GIVEN** tasks written as `- [ ]`, `- [x]` and `- [X]`
- **WHEN** tasks are counted
- **THEN** `- [ ]` is incomplete and `- [x]` and `- [X]` are complete
