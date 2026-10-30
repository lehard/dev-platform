## RENAMED Requirements

- FROM: `### Requirement: Chat coordinator role is a repository-defined observer and exception operator`
- TO: `### Requirement: Chat coordinator role is a repository-defined delivery orchestrator`

## MODIFIED Requirements

### Requirement: Chat coordinator role is a repository-defined delivery orchestrator

The repository SHALL define the chat coordinator role in `docs/engineering/chat-coordinator.md`, reachable from the `AGENTS.md` concern table, as the delivery orchestrator. The coordinator SHALL keep the backlog roadmap (what is taken into work and in which order), SHALL start and hold development streams (at most two code streams unless the owner decides otherwise), and after a developer handoff SHALL launch review, repair and post-merge workers and run LLM-free lifecycle jobs itself until no job remains. It SHALL NOT write code or perform a stream's task. Routine recovery after a technical failure (`resume`, `switch-provider`, `reoffer-post-merge`, `restore-gates`) SHALL need no per-PR owner decision. Material review findings, exhausted review or repair rounds, disputed rejections or dispositions, business decisions and OpenSpec changes SHALL remain the owner's decision; the coordinator SHALL bring them with options, cost or risk and a recommendation, and where an executor's contract needs the owner's own words it SHALL ask the owner and not supply them. It SHALL state facts only from the overview and GitHub, unknown SHALL remain unknown, and it SHALL NOT bypass a live claim, a required check or branch protection, touch another agent's state, worktree or scope, or simulate success. The runbook SHALL let a new session holding only the role reconstruct the current state and next step from GitHub.

#### Scenario: Role assigned in a new session
- **WHEN** the user assigns a new session the chat coordinator role and asks what is going on
- **THEN** the session reads the role document, runs the overview and answers with stages, blockers and next steps with links

#### Scenario: Routine worker run after a handoff
- **WHEN** a developer hands off a PR and its review job is unclaimed
- **THEN** the coordinator launches the review worker without asking the owner

#### Scenario: Material finding
- **WHEN** an item is escalated for a material finding
- **THEN** the session shows the finding with options and a recommendation and asks the owner for the decision
- **AND** it does not run `resume`
