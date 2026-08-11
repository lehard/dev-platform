## Context

Current `managed-task-intake` deliberately keeps the importer free of dispatch and
Project-status mutation. That boundary remains correct: reading/materializing a
package is not the same as claiming work. The supported managed execution entry
point (`start_managed_task`) is the first lifecycle event that proves the task was
actually taken.

The current repository configuration identifies the Development Backlog
repository, `project:*` label and default priority, but it does not yet contain a
stable locator sufficient to mutate the user-level GitHub Project `Status` field.
Implementation preflight selected the Project owner login plus numeric Project
number as the reviewed locator. The runtime resolves the Project/item/field and
single-select option node IDs through GitHub's supported GraphQL API on every
reconciliation; no display title is used as identity.

The active `adopt-gh-aw-process-automation` change also integrates with the
platform-owned completion boundary for its friction checkpoint. This change must
compose with that hook instead of replacing or bypassing it.

## Decisions

### 1. Project status is a projection, not a second execution state machine

The authoritative facts remain the managed Issue/OpenSpec provenance, task
workspace/branch and GitHub delivery state. The Project `Status` is the
human-facing projection of those facts. No local database or independent status
journal is added.

The supported workflow remains:

`Backlog -> Ready -> In progress -> In review -> Done`

with `Blocked` as an exceptional externally-actionable state.

`Backlog -> Ready` is intentionally excluded from automation. It remains the
human authorization boundary.

### 2. Claim is bound to successful managed start

Package discovery/import alone does not claim a task. After the standard managed
start path has validated the task and established its safe task workspace, it
must reconcile the central Project item to `In progress` before implementation
continues.

If Project identity, permission or mutation fails at this boundary, the agent
must not silently continue product implementation while the board still says
`Ready`. The start path returns an actionable, resumable blocker. Exact local
cleanup versus retained resumable workspace is an implementation detail to be
chosen so existing start isolation guarantees are preserved.

### 3. Review state follows real delivery publication

When a managed task has a reviewable task PR created or reused for its exact
current delivery, status becomes `In review`. Waiting for required checks,
automatic merge or manual review is still `In review`; ordinary transient CI wait
is not `Blocked`.

For `pr_merge_mode=auto`, `In review` may be brief but remains truthful. For
manual review it may persist until the human review/merge action is complete.

### 4. Blocked is reserved for a real external stop

`Blocked` is used only when the supported lifecycle cannot continue without an
external action or decision (for example an explicit semantic/product decision,
missing required permission/configuration, or another documented non-self-
recoverable gate). A supported lifecycle/helper must provide the transition and
record a concise reason/evidence link where practical; arbitrary free-form
Project editing is not the normal control path.

On resume, reconciliation derives whether the task should return to
`In progress` or `In review` from the current execution/delivery evidence.

### 5. Done requires terminal reconciliation

A merged GitHub PR is authoritative and is never reclassified as unmerged because
a later Project API call fails. However the managed workflow is not reported as
fully reconciled while its source Project item is stale. The status surface must
be able to distinguish at least `remote merged, Project reconciliation pending`
from complete reconciliation.

Once terminal delivery/reconciliation and source-Issue completion policy have
succeeded, the Project item is `Done`. A green/open PR, draft PR, local tests or a
pushed branch cannot produce `Done`.

### 6. Reconciliation is idempotent and restart-safe

Setting an already-correct status is a no-op. Re-running supported managed
start/status/finish/recovery operations re-reads authoritative remote state and
repairs a stale Project value when mapping is unambiguous. It must not create a
second Project item or duplicate workflow records.

A bounded explicit recovery command/path must also support already-stale managed
tasks from the pre-sync era. It may update only when source Issue identity and
lifecycle evidence are unambiguous; ambiguity is reported for human resolution.

### 7. Project identity is explicit configuration

The platform must carry enough reviewed configuration to resolve the intended
Development Backlog GitHub Project and its `Status` field/options reliably.
Implementation preflight should choose the narrowest stable locator supported by
the current GitHub API/CLI (for example owner plus stable Project identity) and
validate the expected status options `Backlog`, `Ready`, `In progress`,
`In review`, `Blocked`, `Done`.

Do not infer the Project from visible UI position, scrape HTML, or depend solely
on a mutable display title. Missing/invalid configuration or permission is an
actionable setup failure, not a silent downgrade.

The generated configuration therefore carries `project_owner` and
`project_number`. Read/reconcile uses authenticated `gh api graphql`; Project
mutation requires the GitHub CLI `project` OAuth scope (or equivalent token
permission), and failures point to `gh auth refresh -s project`. The resolver
requires exactly one matching Issue item, one single-select `Status` field, and
all six reviewed workflow options before it can mutate anything.

### 8. Lifecycle integration retains resumable ordering

Managed start reconciles `In progress` only after package materialization and
cleans up the newly-created workspace if Project mutation fails. PR publication
creates or reuses the exact-head PR first, then reconciles `In review`; failure
leaves that remote PR as explicit resumable evidence. After a confirmed remote
merge, finish synchronizes local main before reconciling `Done`; a Project API
failure leaves the authoritative merge and synchronized main intact but blocks
cleanup/full completion until retry.

The explicit status helper provides read-only inspection plus `block` and
evidence-derived `resume`. It refuses to infer `Done` from an observed merge;
terminal status stays owned by the ordered finish path.

### 9. Keep execution planes separate

Development Backlog is the human workflow/control plane. The existing machine-
local multi-agent board remains technical workspace/scope coordination. Updating
one must not mirror or duplicate every internal agent-board event into the other.
Quick tasks without a managed source Issue do not participate in Development
Backlog status synchronization.

### 10. Rollout uses the normal platform delivery path

The helper/config/guidance changes are platform-owned and must be included in the
normal immutable release and reviewed Copier rollout. Existing project-owned
configuration/content boundaries remain preserved.
