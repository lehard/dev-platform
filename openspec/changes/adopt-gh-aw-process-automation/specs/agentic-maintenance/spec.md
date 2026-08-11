## ADDED Requirements

### Requirement: Cloud agentic maintenance is additive and bounded

The platform SHALL support an optional GitHub Agentic Workflows maintenance layer that runs in GitHub Actions independently from deterministic local development, CI, publication and release correctness. The initial engine SHALL be Codex authenticated through the repository Actions secret `OPENAI_API_KEY`.

#### Scenario: Local computer is offline

- **GIVEN** the repository has a valid configured agentic workflow and Actions secret
- **WHEN** an issue event or schedule triggers the workflow while no developer computer is running
- **THEN** GitHub Actions runs the maintenance workflow in the cloud
- **AND** no local daemon, cron, launchd job or interactive Codex session is required

#### Scenario: Agentic maintenance is unavailable

- **WHEN** GitHub Actions, `gh-aw`, or the external AI provider is unavailable
- **THEN** deterministic CI, protected-main publication and release workflows remain valid and independently operable
- **AND** the failure is limited to automated maintenance/triage functionality

### Requirement: Agentic workflow execution is pinned and reviewable

The repository SHALL keep human-readable agentic workflow source under version control, compile it with one exact tested `gh-aw` release, and commit the corresponding generated lock workflow required for execution. Updating the `gh-aw` pin SHALL be an explicit reviewed change.

#### Scenario: Workflow source changes

- **WHEN** agentic workflow frontmatter or compiled behavior changes
- **THEN** validation recompiles/checks the workflow with the recorded `gh-aw` version
- **AND** source/lock drift is detected before merge

### Requirement: Cloud agents are read-only with constrained safe outputs

The v1 process-maintenance agent job SHALL NOT receive unrestricted repository write access. GitHub mutations SHALL occur only through explicitly declared and bounded `safe-outputs`.

#### Scenario: Process issue triage executes

- **WHEN** a controlled process/platform-candidate issue triggers triage
- **THEN** the agent may inspect repository and issue context
- **AND** may request only allow-listed label/comment safe outputs
- **AND** cannot edit code, create an implementation pull request, approve, merge, or directly mutate repository contents

### Requirement: Public pilot reads remain public-only

The public `dev-platform` pilot SHALL constrain GitHub MCP reads to public
repositories and retain the gateway secrecy/integrity policy. If a gateway
runtime needs a maintenance override to correctly classify public repository
data, that exact runtime SHALL be reviewable in the source and compiled lock;
the workflow SHALL NOT use a private-to-public data-flow opt-out.

#### Scenario: Public process issue is read for a public safe output

- **WHEN** a workflow reads a labelled `dev-platform` process issue
- **THEN** the GitHub MCP policy permits only public repository data
- **AND** the gateway classifies that public response as eligible for the public safe output
- **AND** no private repository data is made available to the agent or output sink

### Requirement: Process issue triage reuses a maintained upstream pattern

The initial process-issue triage workflow SHALL be imported or adapted from a maintained GitHub Agentic Workflows / `githubnext/agentics` issue-triage pattern rather than implementing a custom unrestricted agent framework.

#### Scenario: A process issue arrives

- **WHEN** a new or materially edited issue matches the platform's process-routing criteria
- **THEN** the workflow classifies the issue using the platform's allow-listed labels
- **AND** may identify a strong likely duplicate
- **AND** may add at most a bounded concise triage comment

### Requirement: Periodic backlog review requires no remembered human ritual

The repository SHALL provide a periodic process-backlog review workflow with a weekly fuzzy schedule and manual dispatch. The review SHALL summarize the open process backlog for a human decision without autonomously starting remediation.

#### Scenario: Weekly review runs

- **WHEN** the scheduled review triggers
- **THEN** it identifies new/unreviewed items, likely duplicates, likely stale/already-resolved items, needs-more-evidence items and ready-for-human-decision items
- **AND** produces one bounded current summary
- **AND** does not require a person to remember a local weekly command

#### Scenario: Review recommends a fix

- **WHEN** the workflow judges an issue ready for remediation
- **THEN** it may recommend a status/label and include the issue in the summary
- **AND** it SHALL NOT modify code, create/merge an implementation PR, accept an OpenSpec change or otherwise self-modify the platform in v1

### Requirement: Agentic maintenance has explicit cost and runtime guardrails

Every v1 agentic workflow SHALL declare a bounded runtime and per-run AI-credit budget suitable for a conservative pilot. Increasing those bounds SHALL be justified by observed run evidence.

#### Scenario: A run approaches its budget

- **WHEN** the workflow reaches its configured `max-ai-credits` or runtime bound
- **THEN** execution is stopped or constrained by the `gh-aw` guardrail
- **AND** the repository does not silently permit unbounded inference spend

### Requirement: Central pilot precedes downstream rollout

This change SHALL enable and validate agentic maintenance only in `lehard/dev-platform`. Managed consumer repositories SHALL NOT receive the workflows until a separate follow-up change is approved after central acceptance.

#### Scenario: Central pilot succeeds

- **WHEN** event-driven triage, scheduled backlog review, safe-output constraints and representative cost evidence have been validated in `dev-platform`
- **THEN** the change may be archived/released centrally
- **AND** downstream deployment remains a separate explicit decision
