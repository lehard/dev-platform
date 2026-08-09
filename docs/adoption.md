# Adoption guide

## Primary interface: one-command onboarding

For a repository owned by the same GitHub account, the normal human action is now:

1. add the repository to the **Dev Platform Bot** GitHub App installation if repository access is restricted to selected repositories;
2. run **GitHub Actions -> Adopt Project -> Run workflow** in `lehard/dev-platform` and enter `owner/name`.

The workflow chooses the process. Do not choose Copier profile, harness mode, publish mode or OpenSpec bootstrap steps manually unless a project has an explicit exception.

The onboarding detector produces one of three repository states:

- `fresh` — no existing Dev Platform metadata or project process markers and the repository is small enough for the low-risk fast path;
- `existing` — the repository has its own agent/OpenSpec/CI process or enough existing code to require reviewed migration;
- `adopted` — Dev Platform metadata is already present.

Repository state is deliberately separate from lifecycle ownership. For a first-time `existing` repository, the adoption planner also derives:

- `workflow_profile` — `standard` unless existing worktree isolation plus agent/scope coordination clearly justify `multi-agent`;
- `harness_mode` — `project` when deterministic lifecycle markers show a coherent repository-owned harness, otherwise `platform`;
- `publish_mode` — `pr` for reviewed existing-project migration.

The result JSON, adoption PR and workflow summary report the derived plan and the detector reasons. Repository size can move a target out of the fresh fast path, but size alone never selects project-owned lifecycle authority.

### Fresh fast path

A fresh repository receives `standard` workflow, platform-owned harness and `direct` publish mode by default. Onboarding:

- renders the exact immutable Dev Platform release with Copier;
- performs safe non-interactive OpenSpec initialization with the expanded workflow set, including verify, without changing the developer's global OpenSpec profile;
- runs platform doctor, OpenSpec lifecycle hygiene, strict OpenSpec validation and selected project checks;
- creates an auditable adoption PR and automatically squash-merges it after those checks pass;
- promotes the repository to `managed` in the central registry.

This path is intended for new or nearly empty repositories. The detector is deliberately conservative: existing `AGENTS.md`, `CLAUDE.md`, `openspec/`, `.github/workflows/`, Dev Platform process files, or repository-size thresholds move the target to the cautious path.

### Existing-project cautious path

An existing repository uses the same **Adopt Project** workflow, but onboarding stops at a normal reviewable PR. Existing OpenSpec/tool files are not destructively initialized during the migration.

If the repository already owns a coherent lifecycle surface, onboarding selects `harness_mode=project` instead of forcing the platform harness. Representative evidence includes project-owned check selection together with merge/publish mechanics, or a broader set of lifecycle entrypoints. Existing worktree isolation plus agent/scope coordination selects `workflow_profile=multi-agent`. This allows a mature repository to be `multi-agent + project`: the platform records and validates the capability contract while the repository keeps its proven implementation.

For `harness_mode=project`, expected project-owned lifecycle collisions are preserved by Copier. Reviewed lifecycle paths are recorded in `.dev-platform.toml` as `project_required_files`, so `platform_doctor.py` can verify that the project contract still exists without owning its implementation. Existing project OpenSpec guidance at `docs/engineering/openspec-workflow.md`, project-specific agent rules, check selectors, board/worktree mechanics, merge/publish helpers and project CI remain authoritative when ownership says they belong to the repository.

Ambiguous ownership fails closed before Copier mutation. Examples include a lone platform-colliding lifecycle file that is not enough to establish a coherent project harness, or an existing platform-owned path such as `scripts/platform_doctor.py` without Dev Platform metadata. The normal path does not silently overwrite these files or treat `.rej` artifacts as a successful migration state; resolve the ownership explicitly or use the manual fallback for an exceptional migration.

After the adoption PR is merged, run **Adopt Project** once more for the same repository. It detects the installed platform and performs only the central `managed` promotion. No second hand-written registry PR is required.

### CI ownership during mature adoption

The generic onboarding runner must not understand or install arbitrary product dependencies.

For `harness_mode=platform`, the platform can run the generated `scripts/select_checks.py` contract, including selected/full platform-managed checks.

For `harness_mode=project`, pre-PR validation is limited to dependency-independent platform/OpenSpec checks: conflict hygiene, `git diff --check`, platform doctor/config health, OpenSpec lifecycle hygiene and strict structural OpenSpec validation. The platform does **not** call a project-owned selector with platform-only flags such as `--execute` or `--full`.

The generated `.github/workflows/dev-platform.yml` follows the same boundary. In project-harness mode it runs shared platform/OpenSpec hygiene only. Existing repository CI remains the authority for product/application validation and is neither replaced nor duplicated by Dev Platform CI. The adoption PR explicitly states when product checks are delegated to repository CI.

### Already adopted

If `.dev-platform.toml` or Copier ownership metadata already exists, onboarding does not recopy the project. It validates the explicit onboarding intent and promotes the repository to `managed` if necessary.

## Local developer readiness

After cloning an adopted project, the normal local preparation command is:

```bash
python3 scripts/dev.py ready
```

`ready` synchronizes the integration branch when it is safe to do so, restores/refreshes the configured OpenSpec integrations for Claude/Codex with the platform workflow set, and runs platform and agent doctors. OpenSpec-generated tool files remain machine-local/generated artifacts rather than platform-owned source. `ready` also records generated integration paths in the clone-local `.git/info/exclude`, so mature repositories do not need platform edits to their project-owned `.gitignore`.

In `harness_mode=project`, repository-owned lifecycle files remain authoritative. Where a mature repository already owns a helper such as `project_sync.py` or `agent_doctor.py`, Copier preserves that helper; `ready` invokes the reviewed repository entrypoint rather than replacing its implementation. Shared platform doctors continue to validate metadata/OpenSpec/platform health.

Agents should prefer this entrypoint over asking the human to remember `project_sync`, OpenSpec init/update, `platform_doctor` and `agent_doctor` separately.

## Manual fallback

Direct Copier operation remains available for platform development, recovery and unusual migrations.

### New repository created locally

```bash
copier copy --trust https://github.com/lehard/dev-platform.git ./new-project
cd ./new-project
python3 scripts/dev.py ready
```

Commit `.copier-answers.yml`; Copier uses it to calculate future template updates.

### Existing repository

Adopt on a dedicated branch or worktree, never directly into a dirty integration branch.

```bash
copier copy --trust https://github.com/lehard/dev-platform.git .
```

Before accepting the result:

- preserve real project-specific agent rules;
- decide explicitly whether lifecycle entrypoints are project-owned or platform-owned;
- move domain rules out of the root platform contract;
- adapt `dev-platform/checks.toml` only when the platform owns the project check contract;
- inspect `.gitignore`;
- run `python3 scripts/platform_doctor.py`;
- run the repository's own product checks when `harness_mode=project`, or the selected/full platform checks when `harness_mode=platform`.

The manual existing-repository path deliberately does **not** auto-run a potentially destructive OpenSpec migration. After reviewing the adoption diff, `python3 scripts/dev.py ready` is the normal local integration refresh.

After the initial adoption is reviewed, `.dev-platform.toml`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `dev-platform/checks.toml`, `openspec/config.yaml` and `docs/engineering/project-rules.md` remain protected from destructive first-time replacement. In `harness_mode=project`, project-owned lifecycle scripts, Git hooks, `.gitignore` and project-specific `docs/engineering/openspec-workflow.md` are also preserved. Platform-owned non-colliding metadata, doctors, OpenSpec lifecycle enforcement and self-contained Dev Platform CI remain managed by the platform.

If the project needs additional compatibility helpers to be mandatory, declare repository-relative paths in `.dev-platform.toml` as `project_required_files = ["..."]` rather than customizing `scripts/platform_doctor.py`.

## Upgrade

For an ordinary manual upgrade:

```bash
copier update --trust
```

Perform upgrades in a dedicated worktree and review the diff. If there is a merge conflict in a platform-managed file, resolve ownership rather than automatically preferring template or project content. Project-owned files should remain unchanged by Copier according to the reviewed harness ownership contract.

Stable Copier renders synchronize `.dev-platform.toml` `platform_version` from `.copier-answers.yml` `_commit`; platform doctor treats disagreement between those records as blocking drift.

Once an adopted repository is `managed`, new stable platform releases are eligible for automatic exact-version Copier rollout PRs. The rollout system still stops at a PR; it does not auto-merge ordinary platform upgrades.

## CI access

Generated downstream CI is self-contained. A managed private project does **not** need GitHub Actions access to execute a reusable workflow from the private `dev-platform` repository. Platform CI changes arrive through reviewed Copier updates instead.

The only cross-repository credential required for onboarding and central automated rollout is the dedicated least-privilege Dev Platform GitHub App described in `docs/managed-rollout.md`.
