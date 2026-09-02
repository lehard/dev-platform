## ADDED Requirements

### Requirement: Web projects can opt into browser verification

Dev Platform SHALL support an opt-in browser verification capability for eligible web
projects that can produce bounded exploratory browser evidence without replacing
repository-owned deterministic browser tests. The capability SHALL reuse the optional
engineering capability lifecycle for identity, opt-in, materialization, provenance and
update/removal and SHALL NOT introduce a browser-specific registry, selection semantics or
materialization path.

#### Scenario: Eligible web project verifies a local flow
- **WHEN** browser verification is enabled for a web project and a controlled local/test flow is requested
- **THEN** the adapter can navigate and inspect the flow and produce bounded evidence of the expected end state
- **AND** deterministic E2E remains the repeatable acceptance authority

#### Scenario: Project has no web capability
- **WHEN** a managed project does not opt into browser verification
- **THEN** ordinary task and verification lifecycle does not require browser runtime installation or execution
- **AND** no browser skill surface, backend dependency or mandatory browser step is materialized

#### Scenario: Mandatory checks do not depend on the exploratory backend
- **WHEN** the platform or a managed project runs its mandatory check suite
- **THEN** the suite passes without the exploratory browser backend installed
- **AND** the browser adapter is not a member of a mandatory CI test group

### Requirement: Browser verification uses bounded origins and session state

Browser verification SHALL default to controlled origins and SHALL keep credentials,
profiles, cookies, cache and sensitive session data out of tracked repository state and
reusable package evidence. Broader non-production origins SHALL require an explicit
project-owned allowlist entry, and production origins SHALL additionally require a per-run
governed authorization.

#### Scenario: Run targets a non-allowed origin
- **WHEN** an exploratory browser run attempts an origin outside the default set and the configured project allowlist
- **THEN** the run fails closed and performs no navigation
- **AND** it does not silently expand to production access

#### Scenario: Run targets a production origin
- **WHEN** an exploratory browser run targets an origin listed as production
- **THEN** the run additionally requires an explicit per-run authorization flag
- **AND** any write or submit intent against that origin is refused

#### Scenario: Browser runtime emits local state
- **WHEN** a run creates profile, cookie, cache or screenshot artifacts
- **THEN** that runtime state is written only under an ignored machine-local directory
- **AND** durable evidence is sanitized so it contains no cookie, credential or profile bytes

### Requirement: Exploratory browser evidence integrates into the existing verification lifecycle

Browser verification evidence SHALL be an input to the existing OpenSpec semantic
verification and `verification.md` receipt. It SHALL NOT create a second completion status,
verification receipt, or acceptance authority.

#### Scenario: Browser evidence supports a change verification
- **WHEN** a change uses browser verification evidence during its verification step
- **THEN** the evidence is referenced from the existing verification receipt
- **AND** no browser-specific completion state is introduced

#### Scenario: Exploratory backend is unavailable
- **WHEN** the exploratory browser backend cannot run in the current environment
- **THEN** the adapter reports an explicit unavailable outcome distinct from a failed flow
- **AND** the change may proceed using deterministic evidence with the gap explained

### Requirement: Exploratory regressions become deterministic coverage only by reviewed work

A regression discovered through exploratory browser verification MAY be promoted into a
deterministic regression scenario, but promotion SHALL be explicit reviewed work and SHALL
NOT be performed automatically.

#### Scenario: Exploratory mode finds a regression
- **WHEN** exploratory verification detects a broken user-visible flow
- **THEN** the adapter can emit a deterministic regression scaffold description
- **AND** it does not modify test files or acceptance suites on its own

#### Scenario: No deterministic seam exists
- **WHEN** a discovered regression cannot yet be reproduced deterministically
- **THEN** the absence of a deterministic seam is explained explicitly in the change evidence
- **AND** the exploratory finding is not silently dropped
