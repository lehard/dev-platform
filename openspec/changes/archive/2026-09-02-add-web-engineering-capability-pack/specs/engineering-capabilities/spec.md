## ADDED Requirements

### Requirement: Stack-specific web guidance is opt-in and bounded

Dev Platform SHALL expose React/Next guidance only to compatible opted-in projects and SHALL use progressive disclosure.

#### Scenario: Compatible project opts in
- **WHEN** a compatible React/Next project enables it
- **THEN** it receives a compact index and loads only relevant pinned rule groups

#### Scenario: Project is incompatible
- **WHEN** a backend-only, non-React or unsupported project is evaluated
- **THEN** the guidance is not applied and no application dependency changes

### Requirement: UI quality review is independent and advisory

Dev Platform SHALL offer read-only evidence-backed review of accessibility and user-visible web quality without creating tasks or replacing acceptance.

#### Scenario: Defect exists
- **WHEN** evidence supports an accessibility, keyboard/focus, form or responsive defect
- **THEN** location, severity, evidence, uncertainty and recommendation are reported

#### Scenario: Surface is healthy
- **WHEN** evidence supports no finding
- **THEN** no cosmetic work is manufactured

### Requirement: Guidance is reproducible and subordinate

Rules SHALL be pinned and updated only through reviewed capability lifecycle, and SHALL NOT override project design rules, redesign automatically or become a merge gate by themselves.

#### Scenario: Upstream publishes a new revision
- **WHEN** an upstream rule source changes after the capability was pinned
- **THEN** the pinned revision, license and content hash stay in effect
- **AND** the new revision is adopted only through a reviewed capability update, never a runtime read of a mutable URL

#### Scenario: Guidance conflicts with a project rule
- **WHEN** capability guidance disagrees with a project design system or repository rule
- **THEN** the project rule and its acceptance tests take precedence
- **AND** the guidance does not trigger an unsolicited redesign or block merge on its own
