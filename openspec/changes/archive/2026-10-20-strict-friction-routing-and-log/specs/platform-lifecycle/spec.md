## ADDED Requirements

### Requirement: Friction routing never substitutes a missing platform destination or label configuration

The friction router SHALL route a `scope=platform` event only to the platform repository configured as `[promotion].repo` in the enabled operator configuration. When that setting is absent or the operator configuration cannot be read, the router SHALL NOT route the event to the project's own repository; it SHALL keep the event local and report an error that names the missing or unreadable setting. A read error of the process label configuration, or an empty or non-string configured label, SHALL be reported as an error and SHALL NOT be replaced by the default label.

#### Scenario: Platform repository is not configured

- **GIVEN** a project whose operator configuration has no `[promotion].repo`
- **WHEN** a recorded `scope=platform` friction event is routed
- **THEN** no issue or comment is created in the project's own repository
- **AND** the event remains pending with a reason that names `[promotion].repo`

#### Scenario: Label configuration cannot be read

- **WHEN** reading the configured process label fails or yields an empty value
- **THEN** the operation reports that configuration error
- **AND** it does not apply the default label in its place

### Requirement: The local friction log is read strictly with position-independent event identity

Reading the local friction log SHALL fail with an error naming the file, and the line when applicable, if the log is unreadable or a non-empty line is not a valid dated event object; it SHALL NOT return an empty or truncated event list in that case. Tolerating a degraded log SHALL be limited to output that reports the gap and to a checkpoint that explicitly accepts the `friction-log` gap. An event recorded without an id SHALL receive an identity derived from its content rather than its position in the file, and an earlier positional reference SHALL resolve to that identity or fail with a named error.

#### Scenario: Malformed line in the log

- **GIVEN** the local friction log contains a line that is not valid JSON
- **WHEN** a command reads friction events without an accepted gap
- **THEN** it fails with an error naming the log file and that line number

#### Scenario: Unreadable log

- **WHEN** the local friction log exists but cannot be read
- **THEN** reading events fails with an error naming the file instead of returning no events

#### Scenario: Explicitly accepted gap

- **GIVEN** the local friction log contains a malformed line
- **WHEN** a checkpoint is recorded with `--accept-gap friction-log`
- **THEN** the valid events are used and the accepted gap is stored in the receipt

#### Scenario: Legacy event identity is stable

- **GIVEN** an event line recorded without an id
- **WHEN** the log is read again after other lines were appended or an earlier line was removed
- **THEN** its identity is the same on every read
- **AND** an attribution recorded under its earlier positional id resolves to that identity
