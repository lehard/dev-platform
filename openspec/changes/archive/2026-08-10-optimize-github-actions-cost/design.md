# Design: Cost-aware CI contract

## Current problem

The present generated workflow subscribes to both `pull_request` and `push` to the main branch. That is safe but wasteful for a solo/private-repository workflow: a reviewed change commonly gets validated on the PR and then immediately validated again after merge. The central platform CI compounds this with a three-entry job matrix in which checkout, Python/Node setup, unit tests, OpenSpec validation and Copier installation are repeated for every profile.

Project-owned workflows add their own cost patterns. Examples observed before this change:

- `Jara_Fin` runs selected PR checks, a full suite after every main push, and a scheduled full suite every day;
- `planner-agent-lab` has a heavy Playwright/frontend quality workflow on both PR and main push, plus two platform-like workflows with overlapping responsibility;
- `etsy` runs an informational Ruff job on `macos-latest` for both PR and main push even though the lint itself is not macOS-specific.

The platform should make the economical path the default without silently taking ownership of project-specific CI.

## Decision 1 — Derive cloud trigger from `publish_mode`

Do not add a new `cloud_ci_mode` setting yet. The repository already declares how verified work is normally published.

### `publish_mode=pr`

Generated Dev Platform CI listens to:

- `pull_request` targeting the configured main branch;
- `workflow_dispatch`.

It does not listen to `push` on main. The PR run is the remote merge gate; running the same platform checks after merge is redundant.

### `publish_mode=direct`

Generated Dev Platform CI listens to:

- `push` on the configured main branch;
- `workflow_dispatch`.

It does not listen to `pull_request` by default. Direct publication already requires local lifecycle/check enforcement before the main ref moves; the cloud run is a post-publish health signal rather than a second pre-merge gate.

This makes one cloud path correspond to one publish path and avoids the common PR + main duplication.

## Decision 2 — Cancel superseded validation runs

Validation workflows add workflow-level concurrency:

```yaml
concurrency:
  group: <workflow>-<pull_request_number_or_ref>
  cancel-in-progress: true
```

For PRs, new commits cancel the older in-progress run for that PR. For direct/main runs, a newer main push may cancel an older validation run because only the newest repository state matters for ordinary CI.

Release publication and managed rollout workflows are excluded from `cancel-in-progress`: release side effects and cross-repository rollout must remain explicit and auditable.

## Decision 3 — Central Platform CI uses one runner for shared checks

The central `.github/workflows/ci.yml` currently repeats common setup and common tests for three matrix entries. Replace that shape with one validation job:

1. checkout/setup Python/setup Node once;
2. compile scripts, validate registry, run unit tests, OpenSpec lifecycle and strict validation once;
3. install Copier once;
4. iterate through `light`, `standard`, and `multi-agent` factory render/upgrade smoke coverage inside the same job;
5. run multi-agent-only adoption/recopy smoke once.

The goal is not to remove profile coverage. It is to remove repeated environment setup and repeated profile-independent tests.

Central Platform CI runs on PR and manual dispatch. Publication itself remains handled by the dedicated VERSION/release workflow.

## Decision 4 — Local verification owns heavy/full checks; cloud CI is the final remote gate

The platform documentation and generated guidance should state this division clearly:

- local agent lifecycle executes the repository's required selected/full checks before publish;
- cloud CI proves the published/reviewed candidate in a clean environment;
- full browser suites, expensive integration suites and periodic health suites should not automatically rerun after a successful PR unless a repository has a reviewed reason.

No local verification requirement is weakened. Cost is reduced by removing duplicate execution, not by making untested changes acceptable.

## Decision 5 — Project-owned CI remains project-owned

`harness_mode=project` already says product/application CI belongs to the repository. This change keeps that boundary.

The rollout may update the generated Dev Platform hygiene workflow, but it must not rewrite `Jara_Fin` product CI, Planner's `quality.yml`, Etsy's `ci.yml`, or other project-owned workflows.

Those repositories get separate reviewed changes. The recommended baseline is:

- PR + manual dispatch for cloud product CI;
- `concurrency.cancel-in-progress=true`;
- no post-merge duplicate if PR CI is authoritative;
- no daily full suite unless there is a concrete production-monitoring need;
- premium OS runners only for OS-specific behavior;
- expensive full suites available through manual dispatch and/or a much lower-frequency schedule if the project explicitly needs one.

## Decision 6 — Branch protection compatibility is checked before removing legacy workflows

A duplicate workflow may exist because an old required status name is still configured. Therefore implementation must not delete a legacy workflow merely because its YAML is redundant.

For each candidate deletion/rename:

1. inspect repository rules/required status checks with available local `gh` credentials;
2. if the old status is required, update the repository rule or preserve a compatibility status until migration is complete;
3. only then delete/disable the duplicate workflow.

If branch-protection metadata is not accessible, fail closed: keep the workflow and optimize only its triggers/concurrency until the requirement can be confirmed.

## Rollout

1. implement and verify in `dev-platform`;
2. archive OpenSpec change and publish a patch release;
3. managed rollout updates only inventory entries with `state=managed`;
4. separately optimize project-owned workflows in high-cost repositories via reviewed PRs;
5. candidate repositories receive platform-generated changes only after their normal adoption transition to `managed`.

## Rollback

The change is configuration-only from the downstream point of view. Rollback is a normal reviewed platform version update or reverting the project-owned workflow PR. Historical workflow runs and repository content are unaffected.