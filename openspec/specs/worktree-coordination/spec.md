# worktree-coordination Specification

## Purpose
Define coordination rules for concurrent task worktrees, scope claims, and safe integration.

## Requirements

### Requirement: Worktree registration has canonical identity

Multi-agent board registration SHALL accept a canonical absolute path for the declared branch and SHALL reject a relative, nested, missing, main-copy or branch-mismatched path with an actionable domain error before it writes shared board state or launches a subprocess.

#### Scenario: Ambiguous relative path is supplied

- **WHEN** a caller supplies a relative worktree path whose resolution is not explicitly defined by the board contract
- **THEN** registration fails with an error explaining that an absolute registered worktree path is required
- **AND** no board entry or worktree mutation is created

#### Scenario: Path and branch do not match

- **WHEN** a path resolves to a worktree whose checked-out branch differs from the declared branch, or resolves to integration main
- **THEN** registration rejects the request before writing state

### Requirement: Lifecycle exposes materially overlapping active scope

The multi-agent lifecycle SHALL compare a task's declared and factual changed-file scope against valid active board entries at registration and before publication. A material overlap SHALL produce a bounded actionable diagnostic before costly validation or remote mutation, without automatically modifying either task.

#### Scenario: Active tasks overlap one file

- **GIVEN** another valid active entry claims or changes a file also claimed or changed by the current task
- **WHEN** the current task registers or reaches publication preflight
- **THEN** the lifecycle identifies the overlapping path and task identity
- **AND** it asks the operator to coordinate or serialize the work
- **AND** it performs no automatic rebase, merge, reset, stash or cleanup

#### Scenario: Active tasks are independent

- **GIVEN** active task scopes do not overlap
- **WHEN** registration or publication preflight runs
- **THEN** no overlap diagnostic blocks the normal lifecycle

### Requirement: Concrete multi-agent scope claims are admission-controlled atomically

For a platform-owned `multi-agent` workflow, the lifecycle SHALL use the canonical task identity and normalized repository-relative scope information from the existing worktree-coordination mechanism to make a race-safe admission decision before the task performs its first implementation change. Admission and recording of a concrete-path claim SHALL be atomic relative to the machine-local coordination state.

#### Scenario: Two tasks race to claim the same concrete file

- **GIVEN** tasks A and B concurrently attempt to claim the same currently free repository-relative file path
- **WHEN** both admission operations execute
- **THEN** at most one task receives `RUN` for that path
- **AND** the other task receives `WAIT`
- **AND** both tasks cannot begin implementation under simultaneous ownership of the same concrete path

#### Scenario: Independent concrete claims are admitted

- **GIVEN** valid active task scopes contain no hard-overlapping concrete file with the current task
- **WHEN** admission runs
- **THEN** the current task may receive `RUN`
- **AND** unrelated tasks remain able to execute concurrently

#### Scenario: A sibling board record has a branch/path mismatch

- **GIVEN** a sibling board entry names a registered worktree whose checked-out branch does not equal its declared branch
- **AND** the current task has no hard overlap with any valid active claim
- **WHEN** the current task starts and requests admission
- **THEN** the mismatch is reported as bounded hygiene information
- **AND** the independent task may receive `RUN` and materialize in its own worktree
- **AND** the lifecycle does not modify the sibling worktree, branch or board entry merely to proceed

#### Scenario: A valid sibling owns the same concrete file

- **GIVEN** a valid active sibling entry owns a concrete repository-relative file also claimed by the current task
- **WHEN** the current task requests admission
- **THEN** the current task receives `WAIT`
- **AND** the diagnostic identifies the sibling task and bounded conflicting path

#### Scenario: Board state cannot be read or locked

- **WHEN** the lifecycle cannot read or acquire the machine-local coordination state safely
- **THEN** admission fails before starting implementation
- **AND** it does not infer that sibling claims are absent

### Requirement: Hard and soft overlap are classified deterministically

The coordination mechanism SHALL distinguish a hard overlap from a soft or potential overlap using normalized repository-relative scope evidence. Except for a declared generated path, an exact concrete file path present in the current task's claim and another active task's concrete claimed or factual scope SHALL be a hard overlap.

#### Scenario: Active task already changes the same file

- **GIVEN** active task A factually changes `template/scripts/_platform_common.py`
- **AND** task B claims that same concrete file
- **WHEN** task B runs admission
- **THEN** task B receives `WAIT`
- **AND** the diagnostic identifies task A and the conflicting repository-relative path

#### Scenario: Only a broad subsystem overlaps

- **GIVEN** task A and task B both mention the same directory, subsystem, or broad glob
- **AND** no exact concrete file conflict is established
- **WHEN** admission runs
- **THEN** the overlap is reported as soft or potential
- **AND** that overlap alone does not force `WAIT`

#### Scenario: Factual scope disproves a broad declared conflict

- **GIVEN** an active task declared a broad scope
- **AND** its available factual changed-file scope contains no concrete path claimed by the current task
- **WHEN** admission classifies the overlap
- **THEN** the broad declaration does not become a hard blocker by itself

#### Scenario: Tasks share only a declared generated file

- **GIVEN** active task A and task B both change `template/dev-platform/platform-manifest.json`
- **AND** that path is declared generated at the observed `origin/<main>`
- **WHEN** task B runs admission or a scope-gate recheck
- **THEN** no hard overlap is reported for that path
- **AND** the advisory warning still lists it

#### Scenario: A task cannot declare its own shared file generated

- **GIVEN** task B adds a generated-file declaration for a file active task A also changes
- **AND** the declaration is absent at the observed `origin/<main>`
- **WHEN** task B runs a scope-gate recheck
- **THEN** the shared file remains a hard overlap

### Requirement: Admission diagnostics are bounded and privacy-preserving

A hard-overlap diagnostic SHALL identify the current managed or quick task, the conflicting active task, and a bounded set of conflicting repository-relative paths. It SHALL follow the existing coordination privacy contract and SHALL NOT expose unnecessary absolute local paths, secrets, or unrelated task state.

#### Scenario: Hard overlap is reported

- **WHEN** admission returns `WAIT`
- **THEN** the result contains enough bounded task/path context to explain the conflict and support a later retry
- **AND** unrelated local machine details are omitted

### Requirement: Known same-file overlap can be acknowledged without falsifying scope

File-level hard overlap SHALL remain a default admission blocker. The platform MAY allow a task to proceed through an explicit bounded acknowledgment when an operator has verified that the concrete same-file overlap is intentionally safe. The acknowledgment SHALL record the current/conflicting task identities, exact conflicting repository-relative paths and a bounded reason, and SHALL NOT require the task to omit those paths from its truthful declared scope.

#### Scenario: Same file is intentionally shared

- **GIVEN** task A is active and claims file `x`
- **AND** task B also truthfully needs file `x`
- **WHEN** task B starts without an overlap acknowledgment
- **THEN** task B receives the normal hard-overlap `WAIT`
- **WHEN** an operator explicitly acknowledges the current A/B overlap on file `x` with a reason
- **THEN** task B may proceed without removing `x` from its declared scope
- **AND** the acknowledgment is retained as bounded coordination evidence

#### Scenario: Acknowledged overlap does not cover new files

- **GIVEN** an acknowledgment covers file `x`
- **WHEN** task B later overlaps task A on previously unacknowledged file `y`
- **THEN** the acknowledgment for `x` does not authorize `y`
- **AND** the new hard overlap requires a new coordination decision

### Requirement: Factual scope is rechecked before costly validation and publication

The platform SHALL compare the task's current factual changed-file scope with active task claims before costly protected validation and again at the publication boundary. A newly observed hard file overlap that is still active and not explicitly acknowledged SHALL block progression instead of remaining a warning-only diagnostic.

#### Scenario: Task scope expands after admission

- **GIVEN** tasks A and B were admitted without a hard overlap
- **WHEN** task B's factual diff later begins changing a concrete file actively claimed by task A
- **THEN** the pre-validation or pre-publication coordination gate stops task B before further costly/delivery work
- **AND** reports the active conflicting task and bounded repository-relative paths
- **AND** requires the overlap to clear or be explicitly acknowledged

#### Scenario: Conflicting task has completed

- **GIVEN** a previous hard overlap existed
- **WHEN** the sibling task is no longer active under the normal board lifecycle
- **THEN** its stale claim does not block the current task
- **AND** resume may proceed after the ordinary recheck

#### Scenario: Only soft scope overlap exists

- **WHEN** two active tasks share only a broad directory, subsystem or other non-file-specific scope
- **THEN** the platform emits a warning
- **AND** does not create a hard coordination blocker solely from that soft overlap

### Requirement: Scope claims use authoritative managed completion state when squash merge removes branch ancestry

Before a managed sibling claim blocks hard scope gating, the platform SHALL be able to reconcile that claim against the exact task's authoritative GitHub publication state. An exact merged PR SHALL be sufficient evidence that the sibling is completed for scope ownership even when squash merge means the feature branch is not an ancestor of `main`.

#### Scenario: Exact sibling PR was squash-merged

- **GIVEN** an active board claim belongs to an exact managed sibling task
- **AND** that task's exact PR is reported `MERGED` by GitHub
- **AND** the feature branch is not an ancestor of `main` because the repository used squash merge
- **WHEN** another task evaluates hard scope overlap
- **THEN** the completed sibling claim does not block the new task
- **AND** the decision does not require branch ancestry to reconstruct the squash merge

#### Scenario: Publication state is ambiguous or unavailable

- **WHEN** the platform cannot prove the exact sibling PR is merged
- **THEN** it retains the existing active claim
- **AND** hard overlap remains fail-closed

### Requirement: Managed validation proves exact task checkout identity

Before executing mandatory managed validation or lifecycle work that creates or consumes completion evidence, the platform SHALL prove that the invocation is bound to the expected managed task checkout using existing canonical managed-task and worktree identity. The proof SHALL include the expected task/change identity, canonical worktree/branch context and current HEAD and SHALL NOT rely on inherited shell cwd or directory naming alone.

#### Scenario: Validation runs from the correct managed worktree

- **GIVEN** a managed task has an isolated canonically registered task worktree and branch
- **AND** local managed task state identifies the same task/change
- **AND** the validation entrypoint is invoked from that exact task checkout
- **WHEN** checkout identity preflight runs
- **THEN** the task/change, canonical worktree, branch and HEAD are accepted
- **AND** the existing factual-scope gate may run
- **AND** selected validation may proceed normally.

#### Scenario: Shell cwd resets to integration main

- **GIVEN** a managed task is active in an isolated task worktree
- **BUT** a mandatory validation entrypoint is invoked from the protected integration checkout on `main`
- **WHEN** checkout identity preflight runs
- **THEN** the command fails before selected tests begin
- **AND** names the expected managed worktree/branch and canonical remediation
- **AND** does not emit successful task validation evidence.

#### Scenario: Validation is invoked from another task checkout

- **GIVEN** managed task A is the task being validated
- **BUT** the command resolves to task B's registered worktree or managed task state
- **WHEN** checkout identity preflight runs
- **THEN** validation fails before selected tests begin
- **AND** no evidence is emitted that can satisfy task A.

### Requirement: Managed validation evidence is bound to the validated checkout

Successful automated validation evidence used for terminal managed completion SHALL identify the managed task/change, validated branch and HEAD, and checkout identity strongly enough to reject evidence produced for a different checkout.

#### Scenario: Green evidence came from the wrong checkout

- **GIVEN** a managed task expects its canonically registered feature worktree/branch
- **AND** an evidence artifact describes a different task/change, checkout, branch or HEAD
- **WHEN** archive or finish evaluates completion evidence
- **THEN** that evidence is rejected as mismatched
- **AND** the task must obtain validation from its exact checkout.

#### Scenario: Task changed after successful validation

- **GIVEN** valid evidence records task HEAD A
- **AND** the task checkout advances to HEAD B before terminal completion
- **WHEN** archive or finish evaluates the evidence
- **THEN** the evidence for HEAD A does not satisfy completion for HEAD B.

### Requirement: Managed checkout identity is observable without mutation

Read-only managed status SHALL surface enough current and expected checkout identity to diagnose wrong-checkout execution without running validation, reconciling branches, changing task state or publishing work.

#### Scenario: Status is invoked from the wrong checkout

- **GIVEN** an exact managed task worktree is registered
- **BUT** status is invoked from integration main or another checkout
- **WHEN** status resolves checkout identity
- **THEN** it reports the mismatch and expected task checkout/branch with bounded remediation
- **AND** performs no validation or mutation.

### Requirement: Integration stray state remains ownership-safe

When managed preflight observes dirty or untracked integration-checkout paths while an isolated task is active, the platform MAY classify paths that are provably owned by the current task and provide bounded remediation. It SHALL NOT automatically clean, reset, stash or delete sibling/foreign/ambiguous task state.

#### Scenario: Current task left its own artifact in integration main

- **GIVEN** an isolated managed task is active
- **AND** integration main contains an untracked or dirty path provably scoped to that same managed change
- **WHEN** managed preflight detects the path
- **THEN** it reports the path as current-task stray state with safe bounded remediation
- **AND** does not generalize that permission to foreign or ambiguous paths.

#### Scenario: Integration state belongs to another task

- **GIVEN** integration main contains state that is foreign, sibling-owned or ambiguous
- **WHEN** managed preflight detects it
- **THEN** the platform preserves the existing hard safety boundary
- **AND** performs no destructive automatic cleanup.

### Requirement: Worktree cleanup eligibility uses authoritative managed completion state when squash merge removes branch ancestry

Before classifying a registered worktree as `not-merged`, the sanctioned cleanup scanner SHALL be able to reconcile that worktree's branch/head against the exact task's authoritative GitHub publication state. An exact merged PR SHALL be sufficient evidence that the worktree is terminally integrated for cleanup eligibility even when squash merge means the feature branch is not an ancestor of `main`.

#### Scenario: Exact worktree PR was squash-merged

- **GIVEN** a registered worktree's exact branch/head PR is reported `MERGED` by GitHub
- **AND** the worktree's branch is not an ancestor of `main` because the repository used squash merge
- **AND** the worktree is otherwise clean, inactive, unlocked and unclaimed
- **WHEN** the sanctioned cleanup scanner classifies that worktree
- **THEN** it is classified eligible for cleanup
- **AND** the decision does not require branch ancestry to reconstruct the squash merge

#### Scenario: Publication state is unavailable, ambiguous, or does not match

- **GIVEN** a registered worktree's branch is not an ancestor of `main`
- **AND** GitHub evidence for that exact branch/head is unavailable, ambiguous, still open, or does not match the worktree's exact head
- **WHEN** the sanctioned cleanup scanner classifies that worktree
- **THEN** it remains classified `not-merged`
- **AND** cleanup does not remove it

#### Scenario: A dirty or active worktree is never removed merely because its PR is merged

- **GIVEN** a registered worktree's exact branch/head PR is reported `MERGED` by GitHub
- **AND** the worktree is dirty, actively in use, locked, or claimed by an active board entry
- **WHEN** the sanctioned cleanup scanner classifies that worktree
- **THEN** it remains ineligible for its original reason (dirty, active process, locked, or active board)
- **AND** the merged-PR evidence does not override those independent checks

### Requirement: Worktree cleanup reports failures truthfully

`worktree_cleanup.py cleanup` SHALL NOT report success for a cleanup that recorded an error or was refused. A targeted cleanup that recorded an error SHALL have status `failed`; a global cleanup that recorded an error SHALL keep status `completed-with-errors`.

#### Scenario: Targeted cleanup fails

- **WHEN** a targeted cleanup cannot remove its deferred worktree and records the error
- **THEN** the result has status `failed` with the error and the command exits non-zero

#### Scenario: Global cleanup with an error

- **WHEN** `cleanup --all --apply` removes some worktrees and records an error for another
- **THEN** the result has status `completed-with-errors` and the command exits non-zero

#### Scenario: Refused global preview

- **WHEN** `cleanup --all` is refused
- **THEN** the command exits non-zero

#### Scenario: Clean cleanup

- **WHEN** a targeted cleanup removes its worktree, or finds it already cleaned, without errors
- **THEN** the command exits zero

### Requirement: Board doctor removes only entries whose merge is proven

When a registered branch is an ancestor of `main`, the board doctor SHALL classify the entry as merged only with proof: either the branch moved on from its registration base and its head is not on main's first-parent line since that base, or the exact task PR is reported merged by GitHub.

#### Scenario: Freshly registered task without commits survives doctor --fix

- **GIVEN** a task registered on the board whose branch was created from the tip of `main`, has no commits and has a clean worktree
- **WHEN** another session runs `agent_board.py doctor --fix`
- **THEN** the entry remains on the board
- **AND** it is not classified `merged-branch`

#### Scenario: Merged and abandoned task is still removed

- **GIVEN** a registered task whose own commits were merged into `main` through a merge commit and whose worktree is clean
- **WHEN** `agent_board.py doctor --fix` runs
- **THEN** the entry is classified `merged-branch` and removed

#### Scenario: Commitless task fast-forwarded over a merge commit survives doctor --fix

- **GIVEN** a registered task without commits whose branch was fast-forwarded to a `main` that gained a merge commit after registration
- **WHEN** `agent_board.py doctor --fix` runs without an exact merged PR for the branch
- **THEN** the entry remains on the board with a named unproven-merge reason

#### Scenario: Unprovable merge is kept with a named reason

- **GIVEN** a registered entry whose branch is an ancestor of `main` but whose merge cannot be proven
- **WHEN** `agent_board.py doctor --fix` runs
- **THEN** the entry remains on the board
- **AND** the doctor output names the reason the merge is unproven

### Requirement: An abandoned candidate worktree is removed only with exact closed-PR proof

Worktree cleanup SHALL provide an explicit operation that removes one exact task worktree, identified by path, branch and head, together with its local branch and its exact agent-board claim, when the candidate was abandoned.

#### Scenario: Closed exact PR

- **GIVEN** a clean, idle worktree whose exact head's PR into main was closed without merge
- **WHEN** the operator runs the abandoned cleanup for that exact worktree, branch and head
- **THEN** the worktree, its local branch and its exact board claim are removed
- **AND** the result is `completed` with exit 0

#### Scenario: PR open, merged or missing

- **WHEN** the branch has an open PR, the exact head has a merged PR, or no closed PR has exactly that head
- **THEN** cleanup refuses naming the reason and removes nothing

#### Scenario: Unsafe local state

- **WHEN** the worktree is dirty, in use, locked, outside the managed directory, its registered branch or head differs from the target, or a board claim names it with another branch
- **THEN** cleanup refuses naming the reason and removes nothing

#### Scenario: GitHub evidence unavailable

- **WHEN** GitHub authentication or the PR list is unavailable
- **THEN** cleanup refuses and removes nothing

### Requirement: Only a valid active board entry with proven identity contributes a blocking concrete-file claim

For a platform-owned `multi-agent` workflow, only a valid active board entry with a proven canonical worktree/branch identity may contribute a blocking concrete-file claim. A degraded or terminal sibling entry MAY produce a bounded hygiene diagnostic, but SHALL NOT by itself make an otherwise independent task wait or fail to start.

#### Scenario: A degraded sibling entry does not block an independent task

- **GIVEN** a platform-owned `multi-agent` workflow and a degraded or terminal sibling board entry
- **WHEN** an otherwise independent task requests admission of its concrete-file claims
- **THEN** the sibling entry contributes no blocking concrete-file claim
- **AND** the sibling entry by itself does not make the task wait or fail to start; at most a bounded hygiene diagnostic is produced

### Requirement: An unreadable or un-lockable coordination store fails admission closed

For a platform-owned `multi-agent` workflow, an unreadable or un-lockable coordination store remains an admission error and SHALL fail closed.

#### Scenario: Coordination store cannot be read or locked

- **GIVEN** a platform-owned `multi-agent` workflow
- **WHEN** the coordination store is unreadable or cannot be locked during admission
- **THEN** admission fails closed as an admission error

### Requirement: The race-safe admission decision results in RUN or WAIT

For a platform-owned `multi-agent` workflow, the admission result of the race-safe admission decision SHALL be:

- `RUN` when no conflicting valid active concrete-file claim is present and the current task has atomically acquired its concrete claims; or
- `WAIT` when a valid active task already owns a hard-overlapping concrete path.

#### Scenario: No conflicting valid active claim

- **GIVEN** a platform-owned `multi-agent` workflow
- **WHEN** no conflicting valid active concrete-file claim is present and the current task has atomically acquired its concrete claims
- **THEN** the admission result is `RUN`

#### Scenario: A valid active task owns a hard-overlapping path

- **GIVEN** a platform-owned `multi-agent` workflow
- **WHEN** a valid active task already owns a hard-overlapping concrete path
- **THEN** the admission result is `WAIT`

### Requirement: Non-concrete scope proximity remains advisory

A shared directory, subsystem, broad glob, or other non-concrete proximity SHALL remain advisory by itself.

#### Scenario: Only non-concrete proximity is shared

- **WHEN** two active tasks share only a directory, subsystem, broad glob or other non-concrete proximity
- **THEN** that proximity by itself is advisory and is not a hard overlap

### Requirement: A path declared generated at the integration branch is a soft overlap

A path the project declares generated in the committed check configuration at the observed remote integration branch SHALL NOT be a hard overlap and SHALL remain reported as a soft overlap.

#### Scenario: Shared path is declared generated at the integration branch

- **GIVEN** a path the project declares generated in the committed check configuration at the observed remote integration branch
- **WHEN** two active tasks share that path
- **THEN** the path is not a hard overlap
- **AND** it is reported as a soft overlap

### Requirement: A generated-path declaration only on a task branch does not change overlap classification

A generated-path declaration present only on a task branch SHALL NOT change the overlap classification.

#### Scenario: Generated declaration exists only on a task branch

- **GIVEN** a path declared generated only on a task branch and not in the committed check configuration at the observed remote integration branch
- **WHEN** overlap is classified for that path
- **THEN** the classification is the same as without the declaration

### Requirement: An unreadable generated-path declaration stops the scope gate

An unreadable generated-path declaration SHALL stop the scope gate instead of being treated as empty.

#### Scenario: Generated declaration cannot be read

- **WHEN** the generated-path declaration cannot be read
- **THEN** the scope gate stops
- **AND** the declaration is not treated as empty

### Requirement: Factual changed-file scope takes precedence over broader declared scope

When an active task has factual changed-file scope, that concrete evidence SHALL take precedence over a broader declared scope for determining hard overlap; the broader declaration MAY still contribute a warning.

#### Scenario: Factual scope is narrower than declared scope

- **GIVEN** an active task with factual changed-file scope and a broader declared scope
- **WHEN** hard overlap is determined against that task
- **THEN** the factual changed-file scope takes precedence over the broader declared scope
- **AND** the broader declaration may still contribute a warning

### Requirement: The managed checkout identity preflight composes with the factual-scope gate and runs early

The managed task checkout identity preflight SHALL compose with the existing factual-scope pre-validation gate and SHALL run early enough that a wrong checkout cannot begin expensive validation or emit successful task evidence.

#### Scenario: Wrong checkout is caught before validation starts

- **WHEN** mandatory managed validation is invoked from a wrong checkout
- **THEN** the managed task checkout identity preflight, composed with the existing factual-scope pre-validation gate, stops it before expensive validation begins
- **AND** no successful task evidence is emitted

### Requirement: Validation evidence from another checkout or HEAD does not satisfy the managed task

For terminal managed completion, a green result for integration `main`, a sibling worktree or an earlier/mismatched implementation HEAD SHALL NOT satisfy the managed task. A commit that only materializes the managed change's exact already-validated OpenSpec archive and its accepted spec delta MAY follow the validated HEAD before publication.

#### Scenario: Green result for a mismatched checkout or HEAD

- **WHEN** a green automated validation result was produced for integration `main`, a sibling worktree or an earlier/mismatched implementation HEAD
- **THEN** it does not satisfy the managed task for terminal managed completion

#### Scenario: Only the archive commit follows the validated HEAD

- **WHEN** the only commit after the validated HEAD materializes the managed change's exact already-validated OpenSpec archive and its accepted spec delta
- **THEN** the validation evidence may still be used before publication

### Requirement: Worktree cleanup merge proof reuses the exact-PR publication primitive

The exact merged PR proof of worktree cleanup eligibility SHALL reuse the platform's existing exact-PR/exact-head publication primitive and SHALL NOT introduce a second completion state model.

#### Scenario: Cleanup scanner proves a squash merge

- **WHEN** the sanctioned cleanup scanner proves that a worktree's exact task PR is merged
- **THEN** it uses the platform's existing exact-PR/exact-head publication primitive
- **AND** no second completion state model is introduced

### Requirement: Merge proof does not bypass the other worktree cleanup eligibility checks

Every other existing worktree cleanup eligibility check (clean, inactive, not locked, no active board/cwd claim, sufficient age) SHALL still apply unchanged regardless of merge proof.

#### Scenario: Merged worktree fails another eligibility check

- **GIVEN** a worktree whose exact task PR is proven merged
- **WHEN** the worktree is not clean, is active, is locked, has an active board/cwd claim or is not old enough
- **THEN** it is not eligible for cleanup

### Requirement: Worktree cleanup exit status reflects errors and refusals

The `worktree_cleanup.py cleanup` command SHALL exit non-zero whenever the cleanup result carries an error or has status `refused` or `failed`, for a targeted and for a global cleanup, and SHALL exit zero only for a successful, already-cleaned or previewed cleanup without errors.

#### Scenario: Cleanup result carries an error or refusal

- **WHEN** a targeted or global `worktree_cleanup.py cleanup` result carries an error or has status `refused` or `failed`
- **THEN** the command exits non-zero

#### Scenario: Cleanup without errors

- **WHEN** `worktree_cleanup.py cleanup` is successful, already cleaned or a preview, without errors
- **THEN** the command exits zero

### Requirement: Board registration records the registration base

Board registration SHALL record the registered branch head as the entry's registration base.

#### Scenario: A branch is registered on the board

- **WHEN** a branch is registered on the board
- **THEN** the registered branch head is recorded as the entry's registration base

### Requirement: A branch still at its registration base is not classified merged

A registered branch that still points at its board registration base has no own commits and SHALL NOT be classified merged by the board doctor.

#### Scenario: Registered branch has no own commits

- **GIVEN** a registered branch that still points at its registration base
- **WHEN** the board doctor classifies its entry
- **THEN** the entry is not classified merged

### Requirement: A board entry whose merge cannot be proven is degraded and kept

When the merge of a board entry cannot be proven, because the entry has no registration base, its base is not a known commit, or the moved branch head lies on main's first-parent line (for example after a fast-forward to a newer `main`) or no longer descends from its base, without an exact merged PR, the board doctor SHALL classify the entry as degraded with a named reason and SHALL NOT remove the entry under `--fix`.

#### Scenario: Merge of a board entry is unprovable

- **GIVEN** a board entry with no registration base, a base that is not a known commit, or a moved branch head on main's first-parent line or no longer descending from its base
- **AND** no exact merged PR
- **WHEN** the board doctor runs with `--fix`
- **THEN** the entry is classified degraded with a named reason
- **AND** it is not removed

### Requirement: Candidate abandonment is proven from GitHub

For the explicit worktree cleanup operation that removes an abandoned candidate's exact task worktree, abandonment SHALL be proven from GitHub: a pull request of the worktree's branch into main whose head is exactly the worktree's head is closed without merge, and no merged pull request with that head and no open pull request exists for the branch.

#### Scenario: Exact pull request closed without merge

- **WHEN** a pull request of the worktree's branch into main whose head is exactly the worktree's head is closed without merge
- **AND** no merged pull request with that head and no open pull request exists for the branch
- **THEN** abandonment is proven

### Requirement: An abandoned candidate head is not contained in main

For the explicit worktree cleanup operation that removes an abandoned candidate's exact task worktree, the worktree's head SHALL NOT be contained in main.

#### Scenario: Candidate head is contained in main

- **WHEN** the worktree's head is contained in main
- **THEN** the abandoned-candidate removal does not remove the worktree

### Requirement: An abandoned candidate worktree is in a safe local state

For the explicit worktree cleanup operation that removes an abandoned candidate's exact task worktree, the worktree SHALL be registered with its identified branch and head, inside the managed worktree directory, unlocked, clean and not in use.

#### Scenario: Candidate worktree local state is unsafe

- **WHEN** the worktree is not registered with its identified branch and head, is outside the managed worktree directory, locked, dirty or in use
- **THEN** the abandoned-candidate removal does not remove the worktree

### Requirement: Abandoned candidate removal refuses on any unmet condition

For the explicit worktree cleanup operation that removes an abandoned candidate's exact task worktree, any unmet condition, unavailable GitHub evidence or ambiguous board claim SHALL refuse with a named reason and a non-zero exit, removing nothing.

#### Scenario: A removal condition is not met

- **WHEN** a condition is unmet, GitHub evidence is unavailable or the board claim is ambiguous
- **THEN** the operation refuses with a named reason and a non-zero exit
- **AND** nothing is removed

### Requirement: Scan and global cleanup do not infer abandonment

Worktree cleanup scan and global cleanup SHALL NOT infer abandonment, and the board doctor's merge-proof rules are unchanged.

#### Scenario: Scan or global cleanup meets a closed-PR worktree

- **WHEN** worktree cleanup scan or global cleanup meets a worktree whose pull request was closed without merge
- **THEN** it does not infer abandonment
- **AND** the board doctor's merge-proof rules are unchanged
