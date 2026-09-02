## ADDED Requirements

### Requirement: Material uncertainty can use an isolated prototype

Dev Platform SHALL offer an optional `bounded-prototype` capability that runs a disposable experiment when an observable experiment can materially reduce unresolved product, UI or technical uncertainty that available evidence cannot settle. The capability SHALL declare the question, the options or hypotheses, and time/iteration/cost bounds before the experiment starts, and SHALL run only in a temporary throwaway workspace or an explicitly project-declared prototype area.

#### Scenario: Experiment is justified
- **WHEN** evidence cannot resolve a material product, UI or technical choice and a bounded experiment can distinguish the options
- **THEN** the capability records the question, options and declared bounds, runs in an isolated area, and returns the observation plus an evidence reference

#### Scenario: Task is clear
- **WHEN** the accepted behavior and approach are already sufficiently clear, or the change is mechanical or a bounded fix with an established approach
- **THEN** no prototype ceremony is added and work proceeds normally

#### Scenario: Bounds are exhausted
- **WHEN** the declared time, iteration or cost bounds are reached or the evidence gathered is insufficient to decide
- **THEN** the capability stops and records the remaining uncertainty and the safest bounded interpretation rather than continuing the experiment

### Requirement: Prototype work does not touch production state

A `bounded-prototype` experiment SHALL NOT modify production source, dependencies, credentials, or managed task state, and SHALL be refused when it would require unapproved credentials, production writes, sensitive data, or wider permissions.

#### Scenario: Experiment stays isolated
- **WHEN** an experiment runs
- **THEN** production source, dependency manifests, credentials and task/lifecycle state are unchanged, and only temporary or explicitly declared prototype-area paths are written

#### Scenario: Authority is prohibited
- **WHEN** the experiment would need unapproved credentials, writes to production systems, sensitive data, or permissions beyond the current scope
- **THEN** it is refused and the boundary is reported instead of being worked around

### Requirement: Prototype output cannot bypass the production lifecycle

Prototype code SHALL be disposable by default and SHALL NOT be promoted automatically into production source. A useful experimental result SHALL be carried forward only as a decision plus bounded evidence, with production implementation entering the ordinary managed OpenSpec lifecycle.

#### Scenario: Prototype informs production work
- **WHEN** an experiment yields a useful decision
- **THEN** production implementation starts through ordinary managed intake, is written against the contract rather than copied from the prototype, and no prototype code is promoted automatically

### Requirement: Prototype evidence is bounded and cleanable

The `bounded-prototype` capability SHALL retain only a bounded decision record — question, options or hypotheses, declared bounds, observation, decision or remaining uncertainty, and an evidence reference or path — with no transcript, secrets, or sensitive payloads. Temporary state SHALL be cleaned by default when the experiment concludes; retention SHALL be explicit and policy-compatible and SHALL NOT make retained artifacts production source.

#### Scenario: Experiment concludes
- **WHEN** a bounded prototype run ends with a decision or exhausted bounds
- **THEN** the bounded decision record and its evidence reference are captured and the temporary workspace or prototype area is cleaned by default

#### Scenario: Retention is requested
- **WHEN** keeping prototype artifacts beyond the run is asked for
- **THEN** retention happens only when explicitly allowed and policy-compatible, and the retained artifacts are still not promoted into production source
