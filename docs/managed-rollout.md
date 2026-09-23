# Managed project rollout

Managed rollout removes the human step of remembering which Copier-managed projects need a new Dev Platform release.

The operating model is:

`platform release -> managed registry -> exact Copier update -> Harness validation -> rollout PR -> downstream CI/review -> merge`

Ordinary rollout never performs first-time adoption and never auto-merges by default. First-time onboarding is handled by the separate **Adopt Project** workflow.

## Registry

Managed rollout is an optional operator capability. Its project inventory and
cross-project write allowlist live in an external operator-owned registry; the
public core does not ship one. `--registry` is an explicit command-line
override. Otherwise commands read `rollout.registry_path` from the external
operator TOML selected only by an enabled project `[operator]` table. A global
environment variable alone cannot enable the operator layer.

States:

- `managed` — adopted and eligible for automatic rollout PRs;
- `candidate` — active software/project repository awaiting Dev Platform adoption;
- `excluded` — known repository intentionally outside adoption/rollout, with a required explanatory note.

Only `managed` enters the ordinary rollout matrix. `candidate` and `excluded` are non-mutating during rollout. Explicit human-triggered **Adopt Project** onboarding is allowed to promote an adopted candidate/excluded repository because that workflow itself is the intentional reclassification action.

Validate locally with:

```bash
python3 scripts/managed_projects.py --registry /secure/operator/managed-projects.json validate
python3 scripts/operator_doctor.py
```

Explicit promotion is also available for recovery:

```bash
python3 scripts/managed_projects.py promote --repository owner/name --default-branch main
```

### CI resolution: a private operator repository

A GitHub Actions runner has no access to an operator's local filesystem, so
**Adopt Project**, **Roll Out Platform** and **Reconcile Stale Managed
Rollouts** each resolve the registry from a dedicated, private
operator-owned GitHub repository instead — never from `lehard/dev-platform`
itself. The public core must never hold `managed-projects.json`: committing
it there would mean every future promotion permanently records the fleet's
real repository names in `lehard/dev-platform`'s public history.

Set the non-secret repository variable `DEV_PLATFORM_OPERATOR_REPOSITORY`
(for example `your-org/dev-platform-operator`) on the public repo to name that
private repository generically — it is never hardcoded in workflow or Python
source. Each workflow then:

1. fails closed if `DEV_PLATFORM_OPERATOR_REPOSITORY` is unset, with the same
   explicit message pattern as the GitHub App configuration check;
2. mints a short-lived GitHub App token scoped only to that repository
   (`contents: read` for rollout/reconcile's read-only matrix planning,
   `contents: write` for Adopt Project's promotion write);
3. checks it out to a local `operator/` path in the job;
4. passes `--registry operator/managed-projects.json` to every
   `scripts/managed_projects.py` invocation, and to every
   `scripts/rollout_supersession.py reconcile` invocation (that subcommand
   independently requires `--registry` to confirm a repository is managed
   before closing any of its PRs). A job that calls `reconcile` on a runner
   separate from its own `plan` job repeats this checkout itself, since job
   outputs do not carry a prior job's checked-out working tree.

The private operator repository needs no special structure: it is not a fork
of Dev Platform and not a second platform, only `managed-projects.json` (this
same schema) plus, optionally, an `operator.toml` mirroring the local one
described above. A local checkout of `lehard/dev-platform` resolves the same
registry by cloning that private repository once and pointing
`rollout.registry_path` in the local external operator TOML at the clone's
`managed-projects.json` — no code change is needed for the local path, since
`--registry`/`registry_path` already accept an arbitrary filesystem path.

## Template ownership boundary

Copier creates the initial repository contract, but not every generated file remains platform-owned forever.

The following files are **project-owned after initial creation** and are preserved on later Copier updates:

- `.gitignore` — repository-specific generated/runtime/editor ignores. The template seeds the baseline only at initial creation; every existing `.gitignore` is preserved byte-for-byte on later Copier updates, regardless of harness mode;
- `AGENTS.md` — project/root agent contract and any project-specific workflow additions;
- `README.md` — product/repository documentation;
- `dev-platform/checks.toml` — project-specific check selection and acceptance commands;
- `openspec/config.yaml` — project/domain context and OpenSpec guidance;
- `docs/engineering/project-rules.md` — project-specific engineering invariants.
- `docs/context/` — reviewed project/domain context.

Shared executable lifecycle scripts, self-contained CI and shared workflow documentation remain platform-managed. For mature `harness_mode=project` repositories, project-specific Git/task harness collision points listed in `copier.yml` are also preserved during guarded recopy. If a project needs an extra file to be required by platform doctor, declare it in `.dev-platform.toml` as `project_required_files = ["..."]` instead of editing `scripts/platform_doctor.py`.

Generated agent integrations do not require platform edits to a mature project's `.gitignore`: `python3 scripts/dev.py ready` records those machine-local patterns in the clone's `.git/info/exclude`.

After Copier renders or updates a stable release, `scripts/platform_bootstrap.py` synchronizes `.dev-platform.toml` `platform_version` from `.copier-answers.yml` `_commit`. Managed rollout and platform doctor both reject a stable-tag state where those two version records disagree.

## One-time GitHub App setup

The repository `GITHUB_TOKEN` is intentionally scoped to `dev-platform`, so cross-repository onboarding and rollout use a dedicated GitHub App.

Create a private GitHub App owned by the `lehard` account, for example **Dev Platform Bot**.

Recommended setup:

1. GitHub account **Settings -> Developer settings -> GitHub Apps -> New GitHub App**.
2. Use a descriptive name and the `dev-platform` repository URL as the homepage URL.
3. Webhooks are not required for this workflow; disable webhook delivery unless another use is deliberately added later.
4. Repository permissions:
   - **Contents: Read and write**
   - **Pull requests: Read and write**
   - **Workflows: Read and write** — required because Dev Platform can update downstream `.github/workflows/*` files
   - Metadata remains read-only as required by GitHub.
5. Do not grant organization/account permissions that rollout does not use.
6. Install the App on **`dev-platform` itself**, the **private operator repository** (see [CI resolution](#ci-resolution-a-private-operator-repository) above), plus repositories intentionally participating in onboarding/rollout. When using **Selected repositories**, adding the target repo is the one normal manual security gate before onboarding.
7. Generate a private key for the App.
8. In `lehard/dev-platform` repository settings add:
   - Actions variable `DEV_PLATFORM_APP_CLIENT_ID` = the App **Client ID**;
   - Actions secret `DEV_PLATFORM_APP_PRIVATE_KEY` = the full generated private key including BEGIN/END lines;
   - Actions variable `DEV_PLATFORM_OPERATOR_REPOSITORY` = the private operator repository, `owner/name`.

Never commit the private key or a long-lived installation token.

Each cross-repository job creates separately down-scoped short-lived tokens: read-only platform source access, target-repository write access, and read/write access to the private operator repository's registry as each workflow needs it. No PAT is required.

## Adding a new project

Normal path:

1. If the App uses **Selected repositories**, add the target repository to the Dev Platform Bot installation.
2. In `lehard/dev-platform`, run **GitHub Actions -> Adopt Project** and enter `owner/name`.

That is the human-facing process. The workflow auto-detects the repository:

- a `fresh` repo is rendered, OpenSpec-initialized, validated, merged and promoted to `managed` automatically;
- an `existing` repo gets a reviewed adoption PR and is not auto-merged; merge it after review, then rerun **Adopt Project** once to perform the mechanical `managed` promotion;
- an already adopted repo is promoted without recopying.

The detector and exact behavior are documented in `docs/adoption.md`.

## Bridging a pre-cutover legacy baseline

`copier update` resolves a managed project's template source (`_src_path` in
its `.copier-answers.yml`) itself, independent of the workflow's own
`platform/` checkout, and clones/caches it locally to compute the 3-way diff
against the project's recorded baseline tag (`_commit`). A fresh-history
canonical repository (see `docs/public-cutover.md`) never contains a
pre-cutover tag, so a project still on one fails rollout with `invalid
reference: <tag>` until that tag is bridged in.

Set the optional, non-secret repository variable
`DEV_PLATFORM_LEGACY_REPOSITORY` (for example `your-org/dev-platform-legacy`,
never hardcoded) to the repository holding the preserved pre-cutover history.
When configured, `rollout_project.py --legacy-repository owner/name`:

1. resolves Copier's own local mirror cache for the project's template
   source (the same cache Copier itself uses, keyed by that source URL);
2. narrows that cache's `origin` fetch refspec to exactly what the current
   rollout still needs from the real canonical remote (branches plus the
   exact version being rolled out), so Copier's own periodic `git remote
   update --prune` refresh of that cache cannot delete a tag it doesn't
   recognize as origin's;
3. fetches only the project's recorded baseline tag from the legacy
   repository into that same cache.

The combined objects live only in the ephemeral CI runner's local cache; no
history is rewritten, no old tag is ever pushed to or published from the
canonical repository, and a project already on a post-cutover baseline never
triggers a legacy fetch at all. The same optional flag applies to the
baseline-equivalence comparison guarded recopy falls back to when a Copier
update leaves reject files on genuinely unchanged platform paths.

## Legacy publication-harness continuity

`scripts/rollout_project.py` ships a generic exact-head publication-safety
migration engine (`migrate_project_publication_safety`) for `harness_mode=project`
repositories whose committed publication harness predates the platform's
exact-head merge-safety contract. The public candidate contains no
company-specific data: it defaults to two synthetic example repository
identities (`example-org/legacy-merge-harness`, `example-org/legacy-publish-harness`)
and no expected fingerprints, so it matches nothing and every other managed
repository rolls out unaffected.

A real downstream repository still mid-migration off such a harness is
operator continuity data, not product behavior: the exact repository identity
and the reviewed SHA-256 fingerprint of its exact historical harness/test
bytes belong only in the external operator TOML, never in public source. Set
them under `[rollout.legacy_harness_migrations]` (see
`docs/operator-config.example.toml`); `main()` loads them once via
`apply_operator_legacy_harness_continuity()` before rollout runs. Without that
configuration `migrate_project_publication_safety` never activates, and a
`harness_mode=project` repository whose harness genuinely needs the migration
fails rollout closed with an actionable "publication-safety compatibility
blocker" diagnostic instead of silently shipping an unsafe merge path -- the
same fail-closed behavior as any other unrecognized harness shape.

## Automatic release rollout

`publish-version.yml` publishes the immutable release and then dispatches `.github/workflows/rollout.yml` with that exact tag.

Before any cross-repository token is created, rollout confirms the requested tag is an actually published **immutable** GitHub Release. A manually entered but unpublished version is rejected.

For every `managed` repository, rollout:

1. obtains a read-only source token for private `dev-platform` access and a separate write-capable token scoped to the target repository;
2. checks for an already-open PR for `dev-platform/rollout-vX.Y.Z`;
3. checks out the current configured default branch;
4. validates Copier ownership/source/version metadata and current version coherence;
5. runs Copier `9.17.0` against the exact `vX.Y.Z` tag with `--conflict rej`;
6. requires post-update version coherence and blocks on `.rej`, Git conflict markers, downgrade attempts, unexpected template source or validation failure;
7. runs only Dev Platform Harness validation (`.rej`/diff hygiene and `scripts/platform_doctor.py`); product/application checks are owned by the downstream rollout PR's normal CI;
8. commits and pushes a deterministic rollout branch without force;
9. opens a normal PR;
10. stops. Merge remains governed by downstream CI/review.

After a validated exact-version rollout PR exists, the workflow reconciles older
bot-owned rollout PRs. A PR is eligible only when its head is exactly
`dev-platform/rollout-vX.Y.Z`, its target is stable SemVer, its base matches the
managed registry, and its author is the configured rollout GitHub App. Titles
never establish ownership. Older eligible PRs are closed only after that newer
PR exists; a rollout preparation failure therefore preserves the prior pending
PR. Branch deletion happens only after GitHub confirms close and is warning-only.

For accumulated debt, run **Reconcile Stale Managed Rollouts** first with
`mode=dry-run`. Its artifacts record every proposed closure for the three
currently managed repositories. Review that exact list, then run
`mode=apply` with `confirm_apply=SUPERSEDE_STALE_ROLLOUTS`. The workflow creates
the same down-scoped GitHub App token per managed target and never creates a
token or mutation for `candidate` or `excluded` entries. When the committed
base is behind, maintenance retains the newest eligible bot-owned rollout PR as
the validated replacement and closes only its older eligible predecessors.

Matrix rollout uses `fail-fast: false`: one blocked project does not prevent clean managed projects from receiving PRs.

## Downstream adoption at task start

A clean rollout PR deliberately stops at review; it does not auto-merge. Left
alone, that PR can sit open indefinitely and a later coding session can start
on the older platform version without anyone noticing.

`template/scripts/rollout_preflight.py` closes that gap on the consumer side.
Every platform-owned `start_task.py` invocation (including through
`start_managed_task.py`) reconciles a pending rollout before creating a new
task branch/worktree:

1. after the ordinary `project_sync.py` fetch, it looks for open PRs whose
   head matches the reserved `dev-platform/rollout-vX.Y.Z` branch contract
   against the configured base branch;
2. ownership is confirmed the same way central rollout automation confirms
   it -- exact repository, base branch, and the automation identity recorded
   in `.dev-platform.toml`'s `[tools.rollout] bot_login` -- never by PR title
   or body;
3. a rollout PR whose required checks are green is merged through ordinary
   non-bypass GitHub policy (`gh pr merge --match-head-commit`, the same
   exact-head guard `project_publish.py` uses for task PRs), then local `main`
   is fast-forwarded before the task branch/worktree is created;
4. pending/failed checks, a conflict, a changed head, or an unconfirmed
   automation identity blocks new work with an explicit, resumable state
   instead of silently starting on the older platform layer.

`tools.rollout.bot_login` is rendered into every project's `.dev-platform.toml`
by the Copier template (it is the same platform-wide GitHub App login used by
central rollout automation, not a secret). An existing project only gains this
field once it adopts the rollout carrying it.

`harness_mode=project` repositories keep their own task/worktree entrypoint;
`agent_doctor.py` still reports pending-rollout state there (read-only) so the
prerequisite is visible without the platform replacing that entrypoint.

## Manual retry

GitHub Actions -> **Roll Out Platform** -> **Run workflow**.

Inputs:

- `version` — exact immutable published tag such as `v1.4.2`; empty uses current `VERSION`;
- `repository` — optional exact `owner/name` to retry only one managed project.

A `candidate` or `excluded` repository is rejected by ordinary rollout even when manually specified; use **Adopt Project** for first-time onboarding/reclassification.

## Repeated-failure alerting

A single blocked rollout attempt is surfaced per-run: an `::error::` annotation, a step-summary blocker, and a `rollout-diagnostic.json` artifact (see `rollout-diagnostic-<project>-<version>`). None of that persists across runs, so a project that keeps failing the same way on every release looked, from the platform's point of view, identical to a project that failed once — that gap let `example-org/example-service` fail 8 consecutive releases before anyone noticed.

`scripts/rollout_failure_streak.py` closes that gap by keeping a durable, cross-run streak count per managed project:

- on every terminal blocked attempt, it opens or updates a `rollout-failure-streak`-labeled issue on `lehard/dev-platform` (one per actively-failing project), incrementing `consecutive_failures` and recording the latest diagnostic category/reason;
- once `consecutive_failures` reaches **3**, it adds a `rollout-alert` label and emits a distinct `::warning::` annotation naming the project, the streak length, and the tracking issue;
- the next time that project's rollout preparation succeeds, the tracking issue is closed with a resolution note (it is not deleted, so it remains a searchable history);
- **Reconcile Stale Managed Rollouts** also observes each managed project's default branch on its daily schedule or during confirmed `apply` mode and closes an open alert when its coherent Copier and `.dev-platform.toml` version records prove recovery at or beyond the issue's last failed release. The scheduled run only plans stale-PR supersession; it never applies it. Unreadable, inconsistent, or stale evidence leaves the alert open and emits a bounded diagnostic.
- an unreadable or missing prior state escalates rather than silently resetting to zero — ambiguity is never treated as "clean."

This runs with the workflow's own default `GITHUB_TOKEN` (`issues: write`), not the cross-repository App token, because it only writes to `lehard/dev-platform` itself. It is strictly additive and best-effort: a failure inside the tracker is surfaced as a warning but never changes the rollout attempt's own pass/fail result, and never pushes, retries, or merges anything.

## Failure handling

The system is intentionally fail-closed.

If an onboarding or rollout job is blocked:

- do not edit `.copier-answers.yml` by hand;
- do not force-push deterministic automation branches;
- inspect the failed job and project ownership conflict;
- resolve project/template ownership in a normal project branch or adoption/update PR;
- rerun the same workflow.

If an open rollout PR already exists for the same version, rollout reports it as already pending and does not rewrite the branch. If the target project is already on the requested version, rollout reports a no-op only when platform version records are coherent.
