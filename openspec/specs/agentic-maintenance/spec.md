# agentic-maintenance Specification

## Purpose
TBD - created by archiving change adopt-gh-aw-process-automation. Update Purpose after archive.
## Requirements
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

The public `dev-platform` pilot SHALL constrain GitHub MCP reads to public repositories and retain the gateway secrecy/integrity policy. If a gateway runtime needs a maintenance override to correctly classify public repository data, that exact runtime SHALL be reviewable in the source and compiled lock; the workflow SHALL NOT use a private-to-public data-flow opt-out.

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

### Requirement: Process review does not create managed work

Process/friction issues SHALL be treated as evidence and advisory maintenance input, not as Development Backlog tasks. Neither triage nor periodic review SHALL create a managed task, publish a `managed-openspec:v1` package, materialize OpenSpec, dispatch an executor or change Development Backlog workflow state.

#### Scenario: Review finds a process issue ready for remediation

- **WHEN** triage or weekly review identifies a likely reusable fix
- **THEN** the workflow may explain the recommendation in bounded process output
- **AND** no managed task is created automatically
- **AND** a later explicit human fixation request is required before the existing managed-task authoring path can create Development Backlog state

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

### Requirement: Periodic process review is freshness-aware

Each periodic process-backlog review SHALL identify the exact target repository state it reviewed and SHALL reconcile open process evidence against bounded current managed-work and recent repository-change context. It SHALL not infer that an old issue is currently actionable merely because its historical text still describes a once-valid problem.

#### Scenario: Weekly review runs after repository changes

- **WHEN** the scheduled or manual process review runs
- **THEN** its report records `reviewed_at`, the exact current `main` SHA and a previous-review boundary
- **AND** it considers a bounded set of relevant managed tasks and recently merged/closed work since that boundary
- **AND** it distinguishes unmanaged active evidence, managed evidence, likely resolved/superseded candidates, needs-more-evidence items and ready-for-human-decision items

#### Scenario: Old problem was fixed after the previous review

- **GIVEN** an open process issue describes a problem that a later merged change may have fixed
- **WHEN** the new review evaluates whether to recommend remediation
- **THEN** it checks current repository/managed-work evidence needed for that judgment
- **AND** it does not recommend a duplicate managed fix solely from the stale issue description

### Requirement: Process review clusters symptoms before recommending work

The periodic review SHALL reason about likely root causes across the bounded evidence set and SHALL report a smaller set of candidate managed changes when multiple issues appear to be symptoms of one cause. Issue count SHALL NOT be treated as required-change count.

#### Scenario: Several issues share one likely root cause

- **WHEN** the review finds strong evidence that several process issues describe different symptoms of one underlying platform defect
- **THEN** it groups them into one bounded root-cause candidate
- **AND** cites the contributing issue numbers
- **AND** still requires explicit human fixation before any managed task is created

### Requirement: Review history is stored in dated reports, not ritual source-issue comments

The periodic review SHALL preserve its dated summary report as the review history and SHALL NOT add a generic reviewed-at comment to every source process issue. Source issues are mutated only by explicit lifecycle transitions or other bounded supported actions.

#### Scenario: Review observes an unchanged evidence issue

- **WHEN** a process issue was reviewed but its lifecycle state did not change
- **THEN** the dated process-backlog report records the review result
- **AND** the source issue receives no ritual review comment

### Requirement: Routed friction issues remain eligible for periodic process review

Every process-friction issue created or updated by the platform router SHALL carry the configured `process` label and SHALL remain discoverable by the periodic process review while open.

#### Scenario: Router creates a new source issue

- **WHEN** a sanitized friction event is routed to a new GitHub issue
- **THEN** the issue is created with the configured `process` label
- **AND** the routing result verifies that the issue is eligible for the weekly source query

#### Scenario: Existing generated issue lacks the label

- **GIVEN** an unambiguously platform-generated open process-friction issue lacks `process`
- **WHEN** bounded reconciliation runs
- **THEN** the label is restored idempotently
- **AND** unrelated issues are not relabeled

### Requirement: Process-friction duplicate discovery is not limited to one issue page or one free-form slug

The router SHALL search the complete bounded/paginated open source set required by its dedupe contract and SHALL provide a bounded duplicate-candidate path when a new event appears to describe an existing root cause under a different category wording.

#### Scenario: Matching issue is beyond the first API page

- **GIVEN** more open issues exist than fit in one GitHub API page
- **AND** the matching open friction issue is on a later page
- **WHEN** the same fingerprint is routed
- **THEN** the existing issue is updated
- **AND** a duplicate is not created because of pagination

#### Scenario: Category wording changes for the same root cause

- **WHEN** a new event uses a different category slug but materially matches an existing root-cause candidate
- **THEN** the routing flow surfaces the bounded existing candidate before creating a distinct issue
- **AND** it does not perform an unsupported opaque semantic merge

