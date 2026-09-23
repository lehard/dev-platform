## ADDED Requirements

### Requirement: Generated agentic review jobs have whole-job deadlines

Each platform-owned gh-aw review source SHALL declare a reasonable whole-agent-job timeout, and its generated GitHub Actions workflow SHALL carry that timeout on `jobs.agent` independently of the agentic execution-step timeout.

#### Scenario: A generated agent job contains non-agent setup or cleanup

- **WHEN** a platform-owned gh-aw workflow is compiled with the pinned compiler
- **THEN** its `jobs.agent` has an explicit timeout below the GitHub Actions platform maximum
- **AND** its agentic execution step retains its own bounded timeout
- **AND** the generated lock is produced from the Markdown source rather than edited directly
