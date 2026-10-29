# chat-coordinator Specification Delta

## ADDED Requirements

### Requirement: The lifecycle overview shows open owner-needed signals

The lifecycle overview SHALL print every open owner-needed signal (question, project, task, age) in a dedicated section, in the default text and in the machine-readable output, so the coordinator sees it in the same refresh in which it is raised. When the board is unconfigured or cannot be read, the overview SHALL say so explicitly instead of omitting the section.

#### Scenario: Signal is visible in the overview
- **GIVEN** an open signal on a task's board entry
- **WHEN** the overview is produced
- **THEN** the signal's question, project, task and age appear in the "Owner needed" section

#### Scenario: Board cannot be read
- **WHEN** the board is unconfigured or unreadable
- **THEN** the overview prints a line stating that owner-needed signals cannot be shown and why
