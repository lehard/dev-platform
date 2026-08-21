# Design: Terminal reconciliation for a recognized project harness

## Decision

Keep `harness_mode=project` ownership intact. The migration uses an exact,
reviewed fingerprint and a structured CLI insertion point in the known
Planner-like `finish_task.py` and publication surface. It installs only the
terminal reconciliation adapter and its self-contained helper dependencies.

The adapter obtains exact PR identity from the current branch/head, requires
GitHub `MERGED` plus the expected head SHA, and resolves task identity solely
from archived/task-local managed provenance. It then calls the existing
managed-status contract to set the matching Project item to `Done` and closes
the Issue as completed. Repeated calls observe the same terminal state and do
not create a PR.

## Failure handling

If GitHub confirms merge but Project/Issue mutation fails, the adapter exits
non-zero with a bounded `pending-reconciliation` diagnostic. The exact PR and
branch are retained. A later normal finish invocation recognizes the exact
merged head and attempts only reconciliation; it never republishes or claims
completion first.

## Rollout safety

Unknown, modified, or structurally ambiguous project-owned harnesses are not
rewritten. The rollout stops before version metadata is advanced. The migration
is idempotent and reconstructable from the reviewed legacy bytes.

## Verification

Use mocked structured GitHub state to prove exact identity, delayed check
registration, post-merge mutation failure, and recovery. Exercise the real
Planner-like compatibility fixture end to end and retain existing rollout,
publication and managed-status suites.
