## MODIFIED Requirements

### Requirement: A business requirement is a durable human-facing object distinct from OpenSpec

Dev Platform SHALL support recording an accepted business requirement as one Development Backlog Issue (`type:requirement`) containing only business-language content, with no OpenSpec proposal/design/tasks required at authoring time.

#### Scenario: Requirement authored without OpenSpec
- **WHEN** a business requirement is accepted for fixation
- **THEN** it is recorded as one `type:requirement` Issue with outcome/context/acceptance-evidence/target-repository content
- **AND** no OpenSpec proposal, design, tasks, or technical decomposition is required to create it

#### Scenario: Requirement receives configured Backlog routing
- **GIVEN** the target repository configures `development_backlog.project_label` and `default_priority`
- **WHEN** `requirement_intake.py create` records a Requirement without an explicit priority
- **THEN** the Issue carries `type:requirement`, exactly the configured `project:*` label and exactly `priority:<default_priority>`
- **AND** creation succeeds only after reading those labels back from the Issue

#### Scenario: Requirement routing is missing or conflicting
- **WHEN** the target repository's project label is not configured in the creating checkout, the Backlog repository disagrees with configuration, or a configured label is unavailable
- **THEN** creation stops before any Issue is created
- **AND WHEN** a created Issue reads back with a different `project:*` or `priority:*` label
- **THEN** the exact Issue is reported and fixation is not reported successful

### Requirement: Business Requirement completion includes a bounded end-to-end retrospective

Before a non-trivial Business Requirement reaches terminal Done, Dev Platform SHALL require a truthful, fresh retrospective of the complete Requirement-first path: accepted Requirement, pre-authoring, handoff/decomposition, mandatory children, and delivery. A clean run MAY record a concise `none` result.

#### Scenario: Significant friction predates children

- **GIVEN** pre-authoring incurred repeated rework or a manual workaround before any child was materialized
- **WHEN** the parent retrospective is performed
- **THEN** the meaningful finding is routed through existing friction evidence and linked to the parent result
- **AND** clean child checkpoints do not erase it

#### Scenario: Cross-child friction survives clean children

- **GIVEN** children each finish cleanly but handoff or decomposition caused duplicate work or conflict between them
- **WHEN** the parent retrospective is performed
- **THEN** the cross-child finding is recorded without fabricating a child failure

#### Scenario: Clean parent and terminal gate

- **WHEN** the full path reveals no new meaningful finding
- **THEN** a concise `none` result suffices
- **AND** missing, stale, ambiguous, or unsupported retrospective evidence blocks parent Done with a recovery action

#### Scenario: Open issue recurs in Requirement delivery

- **GIVEN** a known open process issue is encountered again while delivering a Requirement
- **WHEN** the parent review runs
- **THEN** the recurrence is retained as new occurrence evidence linked to the existing problem
- **AND** the parent does not claim `none` merely because the issue was already known.

#### Scenario: Operator-owned drift is observed

- **WHEN** the agent observes material state drift outside its own ownership during the Requirement path
- **THEN** the review considers it as process evidence regardless of who may repair it.

#### Scenario: Requirement signal is unexplained

- **GIVEN** a workaround event is attributed to the Requirement and not linked or classified
- **WHEN** the parent checkpoint is attempted with `none`
- **THEN** it is refused naming the event.

### Requirement: Business Requirement targets have a supported managed lifecycle

A Business Requirement SHALL enter normal intake or execution only when its target repository can demonstrate the managed OpenSpec child, verification, protected publication and terminal reconciliation path required by that Requirement. Local support requires the target's managed capabilities and required lifecycle entrypoints, in addition to valid Backlog routing and protected publication configuration.

#### Scenario: Unsupported operator repository has routing but no managed lifecycle

- **GIVEN** a target repository can supply a Backlog repository, project label and priority
- **AND** it lacks the managed child and publication lifecycle required for Requirement execution
- **WHEN** a local or connected actor attempts Requirement fixation or execution
- **THEN** the operation stops before normal Requirement progress
- **AND** explains the missing lifecycle support and a supported target checkout or workflow route

#### Scenario: Managed target proceeds

- **GIVEN** a target checkout proves its configured managed OpenSpec and publication lifecycle
- **WHEN** a Requirement is fixed or started for that target
- **THEN** normal Requirement routing and execution remain available

#### Scenario: Explicit operator-managed downstream opt-in proceeds

- **GIVEN** an operator-managed downstream target has explicit integration evidence and the required managed entrypoints
- **AND** its Backlog routing parameters derive from its target checkout configuration
- **WHEN** local or connected Requirement intake checks that target
- **THEN** the target is supported without requiring a committed machine-local operator configuration

### Requirement: Requirement terminal state requires target delivery proof

Requirement terminal reconciliation SHALL require a supported target lifecycle and the existing exact linked-child, archived verification and merged delivery evidence. A manually closed Issue, Project Done field, or empty child set SHALL NOT substitute for that proof.

#### Scenario: Target lacks a terminal path

- **GIVEN** a Requirement Issue appears complete or its work was delivered outside managed execution
- **WHEN** terminal reconciliation cannot prove the target's supported managed lifecycle and exact delivered children
- **THEN** it refuses parent Done and Issue closure
- **AND** reports the missing terminal proof

#### Scenario: Integration main was not fast-forwarded

- **GIVEN** a child's archived change with its verification receipt is merged on remote main
- **AND** the local integration main has not been fast-forwarded to it
- **WHEN** terminal reconciliation runs in the integration checkout
- **THEN** it proves that child's delivery from the fetched remote main commit
- **AND** it leaves the local integration main and working tree unchanged

#### Scenario: Remote main lacks the archive

- **WHEN** the fetched remote main commit has no archived change with a verification receipt for a child, even though the local checkout has one
- **THEN** terminal reconciliation refuses, naming that child

### Requirement: Same-context compaction uses an inspectable economic gate

At a semantic compaction opportunity, the platform SHALL use a simple inspectable gate that considers available evidence about expected future replay avoided and compaction/rebuild overhead or risk. Compaction SHALL occur only when the gate passes. V1 SHALL NOT require a learned optimizer.

#### Scenario: Cheaper static reduction explains the payload

- **GIVEN** a semantic opportunity is reached
- **AND** repeated instructions or unneeded eager capability definitions account for the apparent replay cost
- **WHEN** the advisory gate evaluates the opportunity
- **THEN** it records the cheaper reduction opportunity and evaluates only residual compaction benefit
- **AND** it may keep the current context when that benefit is no longer material

#### Scenario: Expected replay benefit is not material

- **GIVEN** a semantic opportunity is reached
- **BUT** little future replay is expected or compact overhead is not justified
- **WHEN** the economic gate evaluates the opportunity
- **THEN** the workflow keeps the current context
- **AND** records an inspectable no-compact reason where dogfood evidence is enabled

#### Scenario: Expected replay benefit materially exceeds overhead

- **GIVEN** a semantic opportunity is reached
- **AND** available evidence indicates substantial future replay would otherwise continue
- **WHEN** the economic gate passes
- **THEN** the runtime may compact the same live context
- **AND** the decision remains distinguishable from a durable handoff

### Requirement: An own stale ready receipt is superseded on proven head advancement

When Requirement execution records a ready-for-integration receipt for a child and a different receipt already exists at that location, the platform SHALL replace it only when the existing receipt is valid, carries the identical Requirement, child Issue, change and source branch, and its recorded head is a strict ancestor of the new head in the child's repository. Any other existing receipt SHALL continue to block with an actionable diagnostic.

#### Scenario: A failed attempt left the lifecycle's own receipt for an older head
- **GIVEN** a valid ready receipt for the same Requirement, child, change and branch records an ancestor of the current child head
- **WHEN** the supervisor advances again
- **THEN** the receipt is replaced by the receipt for the current head without manual cleanup
- **AND** the result reports the superseded head

#### Scenario: The existing receipt is foreign or ambiguous
- **GIVEN** an existing receipt with a different identity, an unreadable or invalid payload, a head that is not a strict ancestor of the new head, or the same head with different content
- **WHEN** the supervisor writes the ready receipt
- **THEN** the write is refused and the lifecycle stays blocked

### Requirement: Started Requirement is claimed on its card before preparation continues

When Requirement execution starts, the primary Requirement Project card SHALL be projected to its existing nonterminal status as soon as pre-authoring state is durably initialised, and again at the entry of every resume, before duplicate checks, evidence gathering or child materialisation. The claim follows Requirement validation and the check that durable pre-authoring state exists, so an invalid or unsupported Requirement is not claimed, and it SHALL NOT rewrite a terminal `Done` card.

#### Scenario: Card is claimed before slow preparation

- **GIVEN** a Requirement card shows `Ready`
- **WHEN** `requirement_intake.py start` initialises its pre-authoring state
- **THEN** the card shows `In progress` before any later pre-authoring or GitHub-dependent step runs
- **AND** a second agent reading the card during the first agent's preparation sees it as occupied

#### Scenario: Restart continues instead of creating parallel ownership

- **GIVEN** a Requirement has durable pre-authoring state
- **WHEN** `start` or `execute_requirement.py advance` is run again
- **THEN** the existing work is continued and the card reconciliation is idempotent
- **AND** a card still showing `Ready` is repaired to `In progress` at entry

#### Scenario: Failure after durable start does not free the card

- **GIVEN** the Requirement has started and its state is durable
- **WHEN** the card reconciliation or a later step fails
- **THEN** the failure is reported, the state is retained and a rerun converges
- **AND** the platform does not write `Ready`

### Requirement: Verified technical child project routing

Dev Platform SHALL derive technical-child routing from the exact parent Requirement's single `project:*` label and Backlog repository together with the committed target `[development_backlog]` configuration, SHALL reject any contradiction, missing or ambiguous routing input before an Issue is created, and SHALL report materialization success only after read-back proves the child's exact `project:*` label, `type:internal-change` label and parent link.

#### Scenario: Consistent routing

- **WHEN** the parent Requirement label, its Backlog repository and the committed configuration identify the same project
- **THEN** the child is created or exactly reused with that `project:*` label
- **AND** success is reported only after read-back shows `project:*`, `type:internal-change` and the parent link

#### Scenario: Conflicting routing is rejected before publication

- **WHEN** the committed `project_label` or Backlog repository differs from the parent Requirement's
- **THEN** materialization fails naming the Requirement, expected and found values
- **AND** no Issue is created

#### Scenario: Missing or ambiguous routing input

- **WHEN** the parent has no `project:*` label or more than one, or required target configuration or the Backlog label is absent
- **THEN** materialization fails naming the missing or ambiguous input and creates nothing

#### Scenario: Read-back mismatch is not success

- **WHEN** the created or reused child lacks the expected `project:*` label, `type:internal-change` or the parent back-reference on read-back
- **THEN** materialization reports failure naming the child and no success result is produced

#### Scenario: Existing mislabeled child is a visible error

- **GIVEN** an exact-handoff child already exists with a contradictory or absent `project:*` label
- **WHEN** the handoff is retried
- **THEN** materialization fails with the child reference, expected and found labels and manual repair guidance
- **AND** no `project:*` label is added, removed or replaced

#### Scenario: Retry completes only the deterministic internal-change label

- **GIVEN** an exact-handoff child with the correct `project:*` label but missing `type:internal-change`
- **WHEN** the handoff is retried
- **THEN** the missing `type:internal-change` label is added once and re-verified before success

### Requirement: ADD preparation separates product contract from system delta

When preparing an Architecture Design Delta, the agent SHALL classify each candidate against the accepted Business Requirement, accepted OpenSpec and active deltas, project context, code/tests and bounded evidence, and SHALL place it in exactly one destination: an already accepted product contract, an existing authoritative technical contract, a real ADD delta, OpenSpec-level implementation detail, or an open product question.

#### Scenario: Detailed Business Requirement

- **WHEN** the Business Requirement already fixes several user-facing behaviours and rules
- **THEN** the ADD lists only the system-level changes they imply relative to the current system
- **AND** the fixed behaviours are not asked of the human again

#### Scenario: Real system delta

- **WHEN** an accepted behaviour requires a changed event contract, responsibility boundary, data ownership or invariant not set by the sources
- **THEN** the ADD states the difference from the current accepted state, the reason and the impact

#### Scenario: Decision already determined by evidence

- **WHEN** an authoritative existing contract determines the choice
- **THEN** the ADD references it as preserved and asks no human question

#### Scenario: Product uncertainty

- **WHEN** a material product decision is missing for correct development
- **THEN** it is shown as a clarification of the Business Requirement
- **AND** the agent neither decides it nor presents it among architectural alternatives

### Requirement: ADD is presented to the human through one standard read-only projection

Whenever the process shows an ADD to a human for a decision or approval, the presentation SHALL be the output of `add_intents.py render-add` for the current ADD document.

#### Scenario: Open consequential alternative

- **WHEN** the ADD has an open architectural choice with options and a recommendation
- **THEN** the projection shows the options, trade-offs, recommendation and exact subject of decision in state «нужны решения»
- **AND** `approve-add` still refuses until it is resolved

#### Scenario: Product clarification

- **WHEN** the ADD records an open choice of kind product
- **THEN** the projection shows it under a separate heading as a clarification of the Business Requirement

#### Scenario: ADD edited after approval

- **WHEN** the material content of an approved ADD changes
- **THEN** the projection shows «требует актуализации» and the earlier approval is not presented as current
- **AND** after re-approval through the existing mechanism it shows «утверждён» for the new content

#### Scenario: Same ADD from different routes

- **WHEN** two agents or projects render the same ADD content
- **THEN** the output is identical in structure and wording of fixed labels

#### Scenario: No new process machinery

- **WHEN** the standard is delivered
- **THEN** no lifecycle stage, approval gate, semantic validator, decision registry, stored report, separate interface or per-project setting exists beyond the read-only command and the existing ADD fields
- **AND** no claim is made that structural checks prove the design is correct

### Requirement: Requirement retrospective covers delivery by quick PRs

The Requirement retrospective checkpoint SHALL accept a Requirement with no linked managed children when the operator names the merged quick pull requests that delivered it, and SHALL record them in the receipt, which is then checked like any other Requirement retrospective. Each named pull request SHALL be merged. Named quick pull requests MAY accompany managed children for a Requirement delivered partly by quick work.

#### Scenario: Requirement delivered only by quick PRs

- **GIVEN** a Requirement with an empty children block delivered by merged quick PRs
- **WHEN** `requirement_retrospective.py checkpoint --quick-pr owner/repo#N ...` runs
- **THEN** the receipt is recorded with the quick PRs and `check` reports it ready

#### Scenario: No children and no quick PRs

- **WHEN** the checkpoint runs for a Requirement with an empty children block and no `--quick-pr`
- **THEN** it is refused naming `--quick-pr`

#### Scenario: Named PR is not merged

- **WHEN** a named quick PR is not merged
- **THEN** the checkpoint stops naming that PR and records nothing

### Requirement: Execute Requirement refuses advance after a merged composition

When a Requirement's composition pull request from its integration branch into `main` is already merged, `execute_requirement.py advance` SHALL stop before it creates, fetches or pushes the integration branch. The refusal SHALL name the merged pull request, state that advancing would recreate the integration branch and break the post-merge jobs, and name the supported next steps: the coordinator's post-merge jobs for that pull request and the read-only publication status.

#### Scenario: Composition already merged

- **GIVEN** the composition PR #N of `requirement/BR-R` is merged and the branch was deleted
- **WHEN** `advance` runs for the Requirement
- **THEN** it fails naming PR #N and the post-merge job and status commands
- **AND** no `requirement/BR-R` branch is created or pushed

#### Scenario: Composition still open

- **WHEN** the composition PR is open or does not exist yet
- **THEN** advance proceeds as before

#### Scenario: Inventory unavailable

- **WHEN** the pull request list for the integration branch cannot be read
- **THEN** advance fails naming the unavailable inventory and touches no branch

### Requirement: Requirement advance resolves handoff, bundle and child by one key

`execute_requirement.py advance` SHALL resolve a handoff's authored bundle by the handoff id: the bundle directory named after it, or the single bundle whose manifest declares that handoff. The bundle's `change` SHALL name the managed change. A handoff whose bundle is ambiguous or malformed SHALL stop naming the bundles involved.

#### Scenario: Intent and change named differently

- **GIVEN** handoff `I1` whose child was materialized as change `object-client-contract` from bundle `bundles/object-client-contract` declaring `"handoff": "I1"`
- **AND** the handoff was refreshed after materialization
- **WHEN** advance runs
- **THEN** handoff `I1` maps to that child and advance continues without a historical-child error

#### Scenario: Mismatched names

- **GIVEN** the same refreshed handoff and a bundle `bundles/object-client-contract` without a handoff declaration
- **WHEN** advance runs
- **THEN** it fails naming handoff `I1`, the linked child and change `object-client-contract`, and the bundle naming rule

#### Scenario: Two bundles claim one handoff

- **WHEN** two bundle manifests declare the same handoff
- **THEN** advance stops naming both bundles

## ADDED Requirements

### Requirement: A newly created Business Requirement carries configured project and priority labels

A newly created Requirement SHALL carry exactly one `project:*` label and exactly one `priority:*` label resolved from the target repository's existing `[development_backlog]` configuration: `project_label`, and the explicitly requested priority or `default_priority`. No separate routing source or default for these Requirement labels SHALL be introduced.

#### Scenario: Requirement labels come from the target configuration

- **WHEN** a Requirement is created for a target repository
- **THEN** it carries exactly one `project:*` label from `project_label` and exactly one `priority:*` label from the explicitly requested priority or `default_priority`
- **AND** no separate routing source or default is used

### Requirement: Business Requirement creation routing fails closed and is read back

Missing or conflicting routing of a newly created Requirement SHALL fail closed, and creation of the Requirement SHALL be reported successful only after a read-back verifies its `project:*` and `priority:*` labels.

#### Scenario: Routing missing or conflicting

- **WHEN** the routing for a newly created Requirement is missing or conflicting
- **THEN** creation fails closed

#### Scenario: Labels read back

- **WHEN** a Requirement has been created
- **THEN** creation is reported successful only after a read-back verifies its `project:*` and `priority:*` labels

### Requirement: Business Requirement retrospective findings use the friction mechanism

New meaningful process findings of the Business Requirement retrospective SHALL use the existing friction/process-issue mechanism.

#### Scenario: New finding in the Requirement retrospective

- **WHEN** the Business Requirement retrospective finds a new meaningful process finding
- **THEN** the finding is recorded through the existing friction/process-issue mechanism

### Requirement: Technical child post-task retrospective stays independent of the parent retrospective

The existing technical child post-task retrospective SHALL remain independently required and SHALL not be duplicated at parent level.

#### Scenario: Child and parent retrospectives

- **WHEN** a Business Requirement with technical children is retrospected
- **THEN** each technical child post-task retrospective is still required independently
- **AND** it is not duplicated at parent level

### Requirement: Parent Requirement review inspects meaningful process signals

The parent Business Requirement review SHALL inspect meaningful successful manual workarounds, non-default or override actions, manual state changes, recurrences of already open process problems, and observed material drift even when another operator or lifecycle owns the state. A `none` result of the parent review requires this bounded factual path review and remains concise on a clean path.

#### Scenario: Signals owned by another operator

- **WHEN** the parent review runs and a manual state change or observed material drift is owned by another operator or lifecycle
- **THEN** the parent review still inspects it

#### Scenario: Clean path

- **WHEN** the bounded factual path review finds nothing
- **THEN** a concise `none` result is recorded

### Requirement: Parent Requirement review applies the task retrospective signal rules

The parent Business Requirement review SHALL use the same mandatory-signal set, dispositions and evidence-gap rules as the task retrospective for signals attributed to the Requirement during pre-authoring and between children, including legacy events attributed by branch or source issue, and SHALL name an unreadable evidence source instead of treating it as clean.

#### Scenario: Legacy event attributed by branch

- **WHEN** a legacy event is attributed to the Requirement by branch or source issue
- **THEN** the parent review applies the task retrospective mandatory-signal set, dispositions and evidence-gap rules to it

#### Scenario: Unreadable evidence source

- **WHEN** an evidence source for the parent review cannot be read
- **THEN** the parent review names that source
- **AND** it is not treated as clean

### Requirement: Backlog routing alone does not prove Requirement target lifecycle support

Backlog routing labels or operator parameters alone SHALL NOT prove lifecycle support of a Business Requirement target repository.

#### Scenario: Only routing labels present

- **WHEN** a target repository has Backlog routing labels or operator parameters but no other lifecycle evidence
- **THEN** its managed lifecycle support is not considered proven

### Requirement: Requirement target lifecycle support check fails before creation or execution

The Business Requirement target lifecycle support check SHALL use target-owned evidence and SHALL fail before creating a new Requirement or beginning execution of an existing one when support is absent or unreadable.

#### Scenario: Support absent or unreadable

- **WHEN** the target-owned lifecycle support evidence is absent or unreadable
- **THEN** the check fails before a new Requirement is created or execution of an existing one begins

### Requirement: Unsupported Requirement target rejection names evidence and a supported route

A rejection of a Business Requirement target without supported managed lifecycle SHALL identify the missing evidence and an available supported route without silently retargeting or manually closing the Requirement.

#### Scenario: Target rejected

- **WHEN** a Business Requirement target is rejected for missing lifecycle support
- **THEN** the rejection identifies the missing evidence and an available supported route
- **AND** the Requirement is neither silently retargeted nor manually closed

### Requirement: Requirement terminal reconciliation reads verification from fetched remote main

The archived verification evidence for Requirement terminal reconciliation SHALL be read from the tree of a freshly fetched remote main commit, not from the integration checkout, so reconciliation neither depends on nor performs a fast-forward of the local integration main; a failed fetch SHALL stop reconciliation.

#### Scenario: Verification read from remote main

- **WHEN** Requirement terminal reconciliation reads the archived verification evidence
- **THEN** it reads it from the tree of a freshly fetched remote main commit, not from the integration checkout
- **AND** the local integration main is not fast-forwarded

#### Scenario: Fetch fails

- **WHEN** the fetch of remote main fails
- **THEN** reconciliation stops

### Requirement: Compaction advisory checks reducible hot payload before compaction benefit

Before evaluating same-context compaction benefit, the advisory workflow SHALL check whether safely reducible repeated instructions, eager loading of rarely needed tool/capability definitions, or prompt-boundary instability account for the hot payload. The advisory workflow SHALL evaluate compaction against the remaining live-history cost and SHALL NOT grow this check into a general prompt optimizer.

#### Scenario: Hot payload from reducible instructions

- **WHEN** the advisory workflow is about to evaluate compaction benefit
- **THEN** it first checks whether repeated instructions, eager tool/capability definitions or prompt-boundary instability account for the hot payload
- **AND** it evaluates compaction against the remaining live-history cost without becoming a general prompt optimizer

### Requirement: Ready receipt supersession is reported in the execution result

A supersession of an existing ready-for-integration receipt during Requirement execution SHALL be reported in the execution result.

#### Scenario: Receipt superseded

- **WHEN** Requirement execution supersedes an existing ready-for-integration receipt
- **THEN** the execution result reports the supersession

### Requirement: Started Requirement claim adds no status and leaves no free-looking Ready

The platform SHALL NOT add a new status for the interval in which a started Requirement is claimed on its Project card before preparation continues, and no error after the durable start of Requirement execution SHALL write or leave a free-looking `Ready` projection by its own action.

#### Scenario: No new status

- **WHEN** a started Requirement is claimed on its card
- **THEN** the card uses an existing nonterminal status and no new status is added

#### Scenario: Error after durable start

- **GIVEN** Requirement execution has started durably
- **WHEN** a later error occurs
- **THEN** the error path does not by its own action write or leave a free-looking `Ready` projection

### Requirement: A contradictory technical child is not silently relabeled

The platform SHALL NOT silently relabel a contradictory technical child.

#### Scenario: Child labels contradict parent routing

- **WHEN** a technical child's labels contradict its derived routing
- **THEN** the platform does not silently relabel the child

### Requirement: Only material system-level changes appear as ADD deltas

Only a new or changed material system-level contract, boundary, storage, data ownership, invariant, security concern or non-functional behavior relative to the current accepted state SHALL appear as a `new` or `changed` ADD delta.

#### Scenario: Material system-level change

- **WHEN** a candidate is a new or changed material system-level contract, boundary, storage, data ownership, invariant, security concern or non-functional behavior relative to the current accepted state
- **THEN** it may appear as a `new` or `changed` ADD delta

#### Scenario: Other candidate

- **WHEN** a candidate is not such a material system-level change
- **THEN** it does not appear as a `new` or `changed` ADD delta

### Requirement: Business Requirement product behaviour is a constraint in ADD preparation

Product behaviour already defined by the Business Requirement SHALL be used as a constraint in ADD preparation and SHALL NOT be re-presented as an architectural alternative requiring approval.

#### Scenario: Product behaviour already defined

- **WHEN** an ADD candidate is product behaviour already defined by the Business Requirement
- **THEN** it is used as a constraint
- **AND** it is not presented as an architectural alternative requiring approval

### Requirement: Existing technical contracts are referenced as preserved in an ADD

An existing technical contract SHALL be referenced in an ADD as preserved and SHALL NOT be re-offered as a choice.

#### Scenario: Existing technical contract

- **WHEN** an ADD candidate is an existing technical contract
- **THEN** the ADD references it as preserved
- **AND** it is not re-offered as a choice

### Requirement: Code naming and sequencing remain OpenSpec detail

Naming of functions, handlers, files or code sequencing SHALL remain OpenSpec detail.

#### Scenario: Naming candidate

- **WHEN** an ADD candidate concerns naming of functions, handlers, files or code sequencing
- **THEN** it remains OpenSpec detail

### Requirement: A missing product decision is a Business Requirement clarification

A material missing product decision SHALL be marked as a clarification of the Business Requirement, not decided in the ADD.

#### Scenario: Product decision missing

- **WHEN** ADD preparation finds a material missing product decision
- **THEN** it is marked as a clarification of the Business Requirement
- **AND** it is not decided in the ADD

### Requirement: ADD candidate classification is evidence-first agent judgement

The classification of ADD candidates SHALL be the agent's evidence-first judgement and SHALL NOT be a keyword or category gate or require an LLM judge.

#### Scenario: Classifying candidates

- **WHEN** the agent classifies ADD candidates
- **THEN** the classification is its evidence-first judgement
- **AND** no keyword or category gate and no LLM judge is required

### Requirement: A bounded change without a design delta skips ADD

A bounded change without a useful design delta SHALL continue to skip ADD and intents.

#### Scenario: No useful design delta

- **WHEN** a bounded change has no useful design delta
- **THEN** ADD and intents are skipped

### Requirement: The render-add ADD presentation message has a fixed header and delta sections

The output of `add_intents.py render-add` for the current ADD document SHALL be a Russian Markdown message with the Business Requirement reference, target repository, ADD identity and content revision with a state derived from existing facts; a 2–4 sentence summary; a table of only the material `new`/`changed` deltas; what is preserved.

#### Scenario: ADD rendered

- **WHEN** `add_intents.py render-add` renders the current ADD document
- **THEN** the output is a Russian Markdown message with the Business Requirement reference, target repository, ADD identity and content revision with a derived state
- **AND** it has a 2–4 sentence summary, a table of only the material `new`/`changed` deltas and what is preserved

### Requirement: The render-add ADD presentation message has question and risk sections

The Russian Markdown message output by `add_intents.py render-add` for the current ADD document SHALL also contain questions that need the human with options, trade-offs and the recommendation where recorded, with product clarifications shown separately; and risks with one unambiguous next action.

#### Scenario: ADD with questions and risks

- **WHEN** `add_intents.py render-add` renders an ADD with questions for the human and risks
- **THEN** the message shows the questions with options, trade-offs and the recommendation where recorded, with product clarifications shown separately
- **AND** it shows the risks with one unambiguous next action

### Requirement: Empty sections are omitted from the render-add ADD presentation

Sections of the `add_intents.py render-add` ADD presentation without content SHALL be omitted.

#### Scenario: Section without content

- **WHEN** a section of the ADD presentation has no content
- **THEN** the section is omitted

### Requirement: The render-add ADD state is approved only with a current proven approval

The state of the `add_intents.py render-add` ADD presentation SHALL be «утверждён» only when the ADD is structurally valid, approved, its approval digest matches the current content and its freshness is proven; an approval that is stale or whose freshness cannot be proven SHALL render as «требует актуализации».

#### Scenario: Current approval

- **WHEN** the ADD is structurally valid, approved, its digest matches and its freshness is proven
- **THEN** the state is «утверждён»

#### Scenario: Stale or unprovable approval

- **WHEN** the ADD approval is stale or its freshness cannot be proven
- **THEN** the state renders as «требует актуализации»

### Requirement: The render-add ADD state otherwise follows open choices, content and freshness

In the `add_intents.py render-add` ADD presentation, an ADD with an open choice or unresolved contradiction SHALL be «нужны решения»; an ADD without elements or choices SHALL be «предложение»; otherwise, when neither «утверждён» nor a stale or unprovable approval applies, it SHALL be «готов к утверждению» only when its freshness is proven and «требует актуализации» when it is not.

#### Scenario: Open choice

- **WHEN** the ADD has an open choice or unresolved contradiction
- **THEN** the state is «нужны решения»

#### Scenario: Empty ADD

- **WHEN** the ADD has no elements or choices
- **THEN** the state is «предложение»

#### Scenario: Other ADD

- **WHEN** none of the other states applies
- **THEN** the state is «готов к утверждению» when freshness is proven and «требует актуализации» when it is not

### Requirement: The render-add ADD projection is read-only and fails on invalid ADDs

The `add_intents.py render-add` ADD projection SHALL be read-only, SHALL write no file or status, SHALL NOT approve, and SHALL fail explicitly on an ADD that is structurally invalid for any reason other than a stale approval digest.

#### Scenario: Projection runs

- **WHEN** the projection renders an ADD
- **THEN** it writes no file or status and does not approve

#### Scenario: Structurally invalid ADD

- **WHEN** the ADD is structurally invalid for a reason other than a stale approval digest
- **THEN** the projection fails explicitly

### Requirement: The render-add ADD projection content is independent of the invoker

The content of the `add_intents.py render-add` ADD projection SHALL NOT depend on the agent or project that invokes the projection.

#### Scenario: Different invokers

- **WHEN** different agents or projects invoke the projection for the same ADD
- **THEN** the content does not depend on the invoking agent or project

### Requirement: Presenting the render-add ADD projection adds no process machinery

Presenting the `add_intents.py render-add` ADD projection SHALL add no mandatory human stop, no new approval mechanism and no project configuration.

#### Scenario: Projection presented

- **WHEN** the projection is presented to a human
- **THEN** no mandatory human stop, new approval mechanism or project configuration is added

### Requirement: Requirement retrospective refuses a Requirement without children or quick PRs

A Requirement with neither linked managed children nor named quick pull requests SHALL be refused by the Requirement retrospective checkpoint with the next action.

#### Scenario: Nothing delivered it

- **WHEN** the Requirement retrospective checkpoint runs for a Requirement with neither linked managed children nor named quick pull requests
- **THEN** it is refused with the next action

### Requirement: Execute Requirement advance stops on an unreadable integration branch inventory

When the pull request inventory of a Requirement's integration branch cannot be read, `execute_requirement.py advance` SHALL stop naming that unreadable inventory instead of assuming no composition exists.

#### Scenario: Inventory unreadable

- **WHEN** the pull request inventory of the integration branch cannot be read
- **THEN** advance stops naming the unreadable inventory
- **AND** it does not assume that no composition exists

### Requirement: Requirement advance fails on an unmapped nonterminal linked child

When a linked child that is not terminal maps to no current handoff, `execute_requirement.py advance` SHALL fail naming that child, its change and the handoffs left unmapped, with the bundle naming rule as the next action.

#### Scenario: Nonterminal child without handoff

- **WHEN** a nonterminal linked child maps to no current handoff
- **THEN** advance fails naming the child, its change and the unmapped handoffs
- **AND** the bundle naming rule is given as the next action
