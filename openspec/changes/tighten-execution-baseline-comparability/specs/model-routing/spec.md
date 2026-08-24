## MODIFIED Requirements

### Requirement: Baseline reporting exposes decision-quality sample adequacy

The execution-efficiency baseline SHALL distinguish launched executions from verified managed executions. A decision-quality `sufficient` status SHALL NOT be produced solely because the launched-execution count reaches the sample guideline. The first decision-quality gate SHALL require at least 15 verified managed executions and SHALL expose verification/metric coverage so sparse or incompatible evidence remains visible.

#### Scenario: Launch count is high but verification coverage is low

- **GIVEN** at least 15 managed executions were launched
- **AND** fewer than 15 have verified completion evidence
- **WHEN** the baseline report is generated
- **THEN** it remains `insufficient`
- **AND** it reports launched and verified/eligible counts separately.

### Requirement: Cross-runtime counters preserve semantic identity

The canonical efficiency schema SHALL compare a model-request count across runtimes only when each contributing adapter has authoritative evidence that its counted event has that same semantic identity. Runtime-local turn, assistant-message or step counters MAY be retained as bounded evidence but SHALL NOT be silently normalized into a cross-runtime model-request metric. Historical ambiguous counters SHALL remain readable without being upgraded to stronger semantics.

#### Scenario: Runtime event meanings differ

- **GIVEN** two runtimes expose different event types whose one-to-one relationship to model requests is not proven
- **WHEN** efficiency evidence is normalized
- **THEN** the platform does not aggregate those counters as one comparable metric
- **AND** unavailable canonical request counts remain unknown rather than fabricated.
