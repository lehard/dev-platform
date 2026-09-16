## ADDED Requirements

### Requirement: Provider-specific live evals prefer supported native runtime surfaces

When a supported provider exposes a native evaluation surface capable of supplying the evidence required by the provider-neutral capability-eval contract, Dev Platform SHALL prefer a bounded adapter over duplicating that provider's execution, scoring, or report-generation runtime.

#### Scenario: Claude native plugin eval is available and compatible
- **WHEN** the configured Claude Code version exposes a supported `claude plugin eval` command
- **AND** its machine-readable output can truthfully satisfy the required capability-eval evidence
- **THEN** Dev Platform SHALL execute Claude live capability evaluation through that native surface
- **AND** SHALL normalize the result behind the existing provider-neutral schema
- **AND** SHALL NOT add a nested Claude runner merely to duplicate supported native behavior

#### Scenario: Native provider eval cannot satisfy the platform contract
- **WHEN** a native provider eval surface omits evidence required by the canonical capability-eval contract or is unavailable/incompatible
- **THEN** Dev Platform SHALL report the live adapter as unsupported or blocked/unavailable as appropriate
- **AND** SHALL preserve ordinary capability lifecycle and deterministic fixture evaluation
- **AND** SHALL NOT fabricate provider parity through undocumented scraping or unsafe execution workarounds

#### Scenario: Native run cannot authenticate or is missing
- **WHEN** the native provider binary is absent, is older than the exact version confirmed to expose the required eval surface, or the run itself cannot authenticate (a partial/incomplete run reporting an authentication or login failure)
- **THEN** Dev Platform SHALL report the case-level and adapter-level status as `blocked/unavailable`
- **AND** SHALL NOT count any of those cases as a negative (`not-triggered`) trigger outcome

#### Scenario: On-disk eval suite has drifted from the reviewed fixture
- **WHEN** a native adapter run resolves a case whose on-disk prompt content no longer hashes to the fixture's reviewed `prompt_sha256`
- **THEN** Dev Platform SHALL refuse to score that run and SHALL raise an actionable error identifying the drifted case
- **AND** SHALL NOT silently trust or persist the drifted prompt text as evidence

#### Scenario: Bounded evidence from a native adapter report
- **WHEN** a native provider adapter produces a full report (prompts, per-message traces, an HTML report)
- **THEN** Dev Platform SHALL retain only case identifiers, prompt digests, bounded statuses, and adapter provenance in the canonical report
- **AND** SHALL NOT copy the native adapter's prompt text, trace files, or HTML report into platform-owned storage
