## Design

### Durable queue and authority

Use the exact PR as the candidate identity. A machine-readable admission marker in a PR comment binds repository, PR number, original head and base SHA; the GitHub comment id is the stable FIFO key. A queue label makes admitted PRs discoverable. Repeated admission reuses the marker for the same exact candidate. A task-content change requires new local validation and a new admission generation. GitHub PR state is authoritative for merged outcomes. Coordinator comments and labels show queued, active, and blocked outcomes with a reason; these are projections, not an alternative completion ledger.

A repository-owned GitHub Actions workflow listens for admission labels and runs on a schedule to recover missed wakeups. Its repository-wide concurrency group allows one running coordinator. Each run re-reads GitHub state and chooses the oldest eligible marker, rather than trusting the triggering event. A later run can recover after runner loss. The coordinator owns branch update and merge; task agents only admit and observe while queued. It uses the existing GitHub App token so branch updates trigger CI and expected-head merges use the same repository policy.

### Candidate integrity

For the selected PR, prove its current head equals the admitted head or a coordinator-produced descendant recorded for that PR. Fetch latest main. If main descends from the admitted base and its changed paths do not intersect task-owned paths, update the PR branch through a normal merge using GitHub's update-branch API with expected head. A conflict, task-owned head change, or changed relevant base paths blocks the candidate for agent review. After update, re-observe exact head and required `validate` check on that head, including GitHub's strict up-to-date branch policy. Just before merging, re-read main and PR head; if main moved, leave the candidate waiting for a fresh coordinator run. Request merge using GitHub's expected-head guard. GitHub protection remains the final arbiter. External main changes get the same relevance check; unknown provenance never authorizes evidence reuse.

### Recovery and rollout

Admission is idempotent across retries and does not create a second PR. Each worker step re-reads GitHub state, so a crash after branch update, check completion, or merge resumes from the observed exact PR and branch state. A bounded wait reports queued or blocked rather than false Done. Existing `finish` terminal reconciliation remains responsible for local main, board, worktree, Project and Requirement obligations after remote merge. Source configuration enables the queue only once the coordinator workflow is present on authoritative main; this lets the feature PR itself use the existing protected publication path.

### Risks

The workflow needs App contents and PR write rights; a denied mutation blocks that run and remains visible in Actions until the credentials are repaired. GitHub Actions concurrency can replace a pending run, so the schedule is a recovery trigger, not the queue ledger. Comments/labels are mutable, so every merge decision revalidates exact PR, branch and CI state; malformed/ambiguous markers block. The coordinator changes only its selected PR branch, never another agent's local worktree or main directly.
