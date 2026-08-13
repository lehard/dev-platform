## ADDED Requirements

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
