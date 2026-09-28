# TeamAI substitution evaluation

This record follows the
[upstream substitution gate](../upstream-substitution.md). It decides, one
overlapping capability at a time, whether TeamAI (`teamai-cli`) should replace
part of Dev Platform. Each decision rests on sandbox observations. Facts that
come only from earlier desk research are marked *desk research only*.

- Evaluated version: `teamai-cli@0.25.0` (2026-09-28). npm dist-tags at
  evaluation: `latest: 0.25.0`, `beta: 0.26.0-beta.5`. `teamai --version`
  printed `0.25.0`.
- Prerelease observations (roadmap evidence only): no prerelease was installed.
  The 0.26 betas are said to add built-in version-bound skills and model
  profiles (*desk research only*). None of this counts toward a decision.
- Dev Platform revision: `2e7748955d9193cf0fc01245e0d16ca292ea9589`.
- Sandbox: disposable directory under the session scratchpad. Every `teamai`,
  `npm`, `git` and rendered-project command ran with the following isolation:
  - `HOME`, `npm_config_prefix`, `npm_config_cache` and `GIT_CONFIG_GLOBAL`
    pointed inside the sandbox;
  - `CI=1` and `TEAMAI_NONINTERACTIVE=1` were set;
  - `GITHUB_TOKEN`, `GH_TOKEN` and `GITLAB_TOKEN` were unset;
  - `DO_NOT_TRACK=1` was set.

  The package was installed with `--ignore-scripts`; it declares no install
  scripts. Stub executables for `claude`, `codex`, `codebuddy` and other agent
  CLIs were put first on `PATH`. They log every call and exit non-zero, so no
  nested provider CLI could run.

  The team repository was a local bare Git repository. It was reached through a
  sandbox-only `url.<bare>.insteadOf https://team.invalid/pilot/team.git`
  rewrite, because `teamai init` rejects local paths (see
  [the shared-resources section](#capability-shared-agent-resources-and-their-distribution)).

  Mutating defaults were disabled in the team `teamai.yaml`:
  - `autoUpdate: false`;
  - `usageReport: false`;
  - `sharing.env.injectShellProfile: false`;
  - `sharing.hooks.autoApply: false`;
  - `sharing.mcp.autoApply: false`;
  - `sharing.recall.enabled: false`;
  - `sharing.contributeHint.enabled: false`;
  - no `scripts.postPull`.

  Each project's local config also set `updatePolicy: skip`,
  `recallEnabled: false` and `contributeHintEnabled: false`. Recall was
  switched on only inside the learnings probe, and `usageReport` only for one
  pull that measured it.

  The installed package ships no `docs/usage-guide.md` and no `src/`. The
  configuration keys were read from the `src/types.ts` module embedded in
  `dist/index.js`.
- Sandbox diff result: findings. Before and after every scenario, file lists
  with SHA-256 hashes were taken of the sandbox home and of each scenario
  project, then diffed.

  Persistent TeamAI writes stayed inside the sandbox home, the scenario
  projects and the sandbox team remote. There were four exceptions:
  - `teamai import` created a transient `$TMPDIR/teamai-extract-*` directory in
    the OS temp directory and removed it;
  - `teamai init` against an unknown HTTPS host starts an HTTP probe
    (`<host>/users/sign_in`) to detect GitLab, which failed on DNS for
    `team.invalid`;
  - the Stop hook and `teamai update --check` queried the npm registry for the
    latest version even with `updatePolicy: skip`;
  - `teamai codebase --extract` tried to launch `claude -p` five times.

  Before and after the pilot, hashes were compared for:
  - the operator's `~/.zshrc`, `~/.zprofile`, `~/.bash_profile` and
    `~/.gitconfig`;
  - `~/.codex/config.toml`;
  - the absent `~/.claude/settings.json`, `~/.codex/hooks.json`, `~/.teamai`
    and `~/.hermes`;
  - the skill-directory listings.

  All were unchanged.
- Scenarios:
  - Dev Platform workflow: a `git clone --local` copy of this repository at the
    evaluated revision. `browser-verification` was enabled, and the ignored
    local `.dev-platform.toml` was copied in with the operator table disabled.
    `capability_manager.py sync`/`audit` and `platform_doctor.py` ran before
    and after `teamai init`/`pull` with the `claude` and `codex` targets.
  - Fresh managed-project render: Copier 9.18.2 from a `git archive` of the
    same revision, with `workflow_profile=standard` and
    `agent_tools=claude,codex`. `--skip-tasks` was followed by a manual
    `platform_bootstrap.py`, after giving the render directory group-`staff`
    setgid permissions required by the shared-workspace preflight.
    `repository-hygiene` was enabled. Capability sync, audit and doctor ran
    before and after `teamai init`/`pull`, and the scenario ended with
    `teamai uninstall`.

## Capability: shared agent resources and their distribution

| Field | Evidence |
| --- | --- |
| Decision | `reject-for-now` |
| Observed behavior and acceptance outcome | Skills, rules, agents, env and a `claudemd/` block reached `.claude/` and `.codex/` in both scenarios. `AGENTS.md` and root `CLAUDE.md` were never modified; the managed block went to `.claude/CLAUDE.md`. Capability sync, audit and doctor gave the same results before and after TeamAI when names did not collide. **Pinning:** a skill vendored as a Git submodule pinned at `v1` was delivered as `v1` while its source had `v2`. The team repository itself cannot be pinned: checking out tag `v1` in the local clone was undone by the next `pull` ("reset to origin (diverged)"), and a rule edited on the default branch reached projects on the next pull. **Collision:** a team skill named `dev-platform-browser-verification` silently overwrote the capability-owned surface. `capability_manager.py audit` then reported `status: error`; `sync` restored it and `pull --force` overwrote it again. Removing the colliding skill from the team repository left the overwritten copy in place. Acceptance: fails. Distribution cannot be pinned to an immutable Dev Platform release, and TeamAI does not respect platform-owned surfaces. |
| Lifecycle coupling | Negative. The SessionStart hook runs `teamai pull`, so what an agent receives changes whenever the team default branch changes, not with a Dev Platform release. `init` registered the member and pushed a `teamai-reports` orphan branch to the team remote. |
| Migration cost | High. An adapter would need an ignore contract for `.codex/rules`, `.codex/skills/<team>` and `.codex/agents` (the rendered `.gitignore` left these as untracked `?? .codex/`), a reserved-name guard against `dev-platform-*`, and a pinned mirror of the team repository. |
| Release cadence and churn | 25 stable and 50 prerelease npm versions. Stable releases landed roughly weekly: 0.23.0 on 2026-09-08, 0.24.0 on 2026-09-14, 0.25.0 on 2026-09-22. The CHANGELOG shipped in 0.25.0 stops at 0.23.0 plus a large `[Unreleased]` section. |
| Security and privacy (what leaves the machine, command surfaces) | `init` applied the team `SessionStart` hook to sandbox `~/.claude/settings.json` and `~/.codex/hooks.json` even with `sharing.hooks.autoApply: false`, because the flag gates only `pull`. The next `pull` removed it again. The hooks live in the HOME-level settings files, not in project settings, and run `bash -lc "teamai hook-dispatch …"` on SessionStart, Stop, PostToolUse and UserPromptSubmit for every session on the machine, guarded by `$PWD`. MCP stayed pending with `autoApply: false`. The shell profile was not modified. |
| Failure and rollback behavior | `teamai uninstall --force` in the managed project removed **all** TeamAI hooks from the shared HOME settings, including the other project's, which kept its synced files. It left behind: the `teamai` skill in `.claude/skills` and `.codex/skills`; `settings.json`/`hooks.json` with empty hook arrays; and `~/.teamai` data (`usage.jsonl`, `votes/`, `dashboard/events.jsonl`, session caches). A second uninstall in the Dev Platform copy left the same residue. Neither project nor HOME returned byte-for-byte to its pre-TeamAI state. |
| Codex / Claude compatibility | Claude: skills, rules, agents and the `.claude/CLAUDE.md` block were delivered. Codex: skills were delivered; rules were copied as Markdown into `.codex/rules/`; agents appeared only after recall was enabled. Codex hooks need a manual trust step (`teamai doctor` says so). Neither agent was launched, so whether Codex reads Markdown rules from `.codex/rules/` is unknown. |
| Ownership classification | Dev Platform-owned |
| Maintenance-surface baseline (source / tests / docs lines) | 1133 / 763 / 342: `capability_manager.py` 537 + 4-line shim, `capability_evals.py` 536 + 4, `project_sync.py` 48 + 4; `tests/test_capability_manager.py`; `docs/engineering/engineering-capabilities.md`. There are also 31 descriptor files under `dev-platform/capabilities/` (1621 lines of reviewed content). |
| Retirement set (adopt) or retention evidence (keep) | Retention evidence: team resources follow the mutable default branch; reference pinning works only per submodule; name collisions silently overwrite capability surfaces and fight capability sync; `init` bypasses the hook opt-out; uninstall is machine-wide and incomplete. Each of these conflicts with immutable release, controlled rollout and a single owner per surface. |
| Projected maintenance reduction (adopt) | not applicable |

## Capability: version-bound or on-demand skills and instructions

| Field | Evidence |
| --- | --- |
| Decision | `watch-only` |
| Observed behavior and acceptance outcome | On stable 0.25.0, `teamai skill` offers only `list`, `show` and `exclude`. There is no install-by-version or on-demand activation. `skill list` listed both the root `pilot-skill` and the `alpha` namespace override under the same name. The only version binding observed was the Git-submodule pin described above. Built-in version-bound skills exist only in 0.26 betas (*desk research only*; not installed). Acceptance: the capability is not available on stable. |
| Lifecycle coupling | Built-in `teamai` and `team-wiki-codebase` skills were written into both projects at `init` and are tied to the installed CLI version, not to a Dev Platform release. |
| Migration cost | unknown; the stable capability is absent. |
| Release cadence and churn | Same as shared resources. The feature is in prerelease churn. |
| Security and privacy (what leaves the machine, command surfaces) | The built-in `team-wiki-codebase` skill ships Python scripts (`scan_repo.py`, `validate_kb.py`) into project skill directories. |
| Failure and rollback behavior | Uninstall left the built-in `teamai` skill behind in both projects. |
| Codex / Claude compatibility | Built-in skills were written identically to `.claude/skills` and `.codex/skills`. |
| Ownership classification | Dev Platform-owned |
| Maintenance-surface baseline (source / tests / docs lines) | Shared with the shared-resources area: descriptor provenance (`revision` + `content_sha256`) is enforced by `capability_manager.py` and delivered through releases. Additional docs: `docs/release-policy.md` 56. No separate module. |
| Retirement set (adopt) or retention evidence (keep) | Stable has no version-bound skills. A prerelease-only capability cannot be `adopt-next-step`. Dev Platform descriptors already bind content to a reviewed revision and hash; TeamAI's stable skill distribution does not. |
| Projected maintenance reduction (adopt) | not applicable |

## Capability: project and team learnings and recall

| Field | Evidence |
| --- | --- |
| Decision | `reject-for-now` |
| Observed behavior and acceptance outcome | `teamai contribute --file` committed the learning **directly to the team remote** on a `teamai-learnings` orphan branch, under `learnings/devplatform/…`. There was no review step. With recall disabled, search returned nothing. After `teamai recall enable`, the project got a `teamai-recall` rule, subagent and `teamai-share-learnings` skill; searching three keywords returned the learning (score 14.7), but a single-keyword query did not. Part of the recall output is fixed Chinese boilerplate. Project isolation held: from the `managed` project `--check` scored 0.0; after switching the directory to `devplatform` it scored 4.3. `recall disable` removed the rule and agent. Acceptance: it works as a knowledge store, but it does not replace the friction pipeline. |
| Lifecycle coupling | Negative. Learnings are written to the shared remote at contribution time, outside the managed task/OpenSpec lifecycle and without a sanitized, fingerprinted process-issue route. |
| Migration cost | High. `agent_friction.py` routes to deduplicated process issues; TeamAI has no issue routing, so both mechanisms would have to coexist. |
| Release cadence and churn | Recall and learnings are beta per *desk research*. The shipped `[Unreleased]` notes change project-private learnings isolation. |
| Security and privacy (what leaves the machine, command surfaces) | Contributed text is pushed verbatim to the team repository. Enabling recall injects an always-apply rule telling agents to invoke the `teamai-recall` subagent before tasks. |
| Failure and rollback behavior | `recall disable` removed its rule and agent. Contributed learnings stay on the remote branch, and uninstall does not touch them. |
| Codex / Claude compatibility | The recall rule was written to both `.claude/rules` and `.codex/rules`; the subagent went to `.claude/agents` and `.codex/agents`. |
| Ownership classification | Dev Platform-owned |
| Maintenance-surface baseline (source / tests / docs lines) | 1134 / 725 / 40: `agent_friction.py` 1130 + 4-line shim; `tests/test_friction_review.py`; the "Friction routing" section of `docs/engineering/agent-workflow.md` (lines 192–231). |
| Retirement set (adopt) or retention evidence (keep) | Unreviewed direct push of free text to a shared remote, no sanitization or issue routing, and recall activation through always-apply rules. These are privacy and coupling problems, not the existence of `agent_friction.py`. |
| Projected maintenance reduction (adopt) | not applicable |

## Capability: codebase knowledge or wiki

| Field | Evidence |
| --- | --- |
| Decision | `reject-for-now` |
| Observed behavior and acceptance outcome | `teamai codebase --extract .` ran in 3.7 s on the Dev Platform copy: 200 files, 1793 facts, 239 nodes and 486 edges, written to an unignored `teamwiki/` tree (888 KB) in the project root. **Without `--deep-enrich`** it still tried `claude -p` five times, passing module context in a Chinese prompt; the stub blocked it ("5 AI task(s) failed"). The documented no-AI path, `teamai import --dir . --skip-enrich --all`, made no provider call. It wrote the graph into the team clone, committed it to the default branch, and tried to push. The push failed only because an earlier pinning probe had left the clone detached, yet the CLI still printed "Pushed to team knowledge repo". Deep enrichment was not exercised: the nested provider CLI is excluded by platform policy. Acceptance: fails. |
| Lifecycle coupling | Negative. The knowledge graph is auto-committed and pushed to the team default branch, not tied to a reviewed revision of the source repository. |
| Migration cost | High. `project_context`/`project_evidence` are revision-bound and never call a provider; replacing them would need a provider-free, non-publishing TeamAI mode that 0.25.0 does not offer by default. |
| Release cadence and churn | Codebase/wiki is beta per *desk research*. |
| Security and privacy (what leaves the machine, command surfaces) | The default extraction tries to send code context to a local agent CLI, which would reach that provider. Import auto-pushes the graph to the shared remote. |
| Failure and rollback behavior | `teamwiki/` in the project is not removed by uninstall; it was deleted by hand. The transient temp directory was cleaned up. |
| Codex / Claude compatibility | The enrichment path shells out to `claude`. Codex enrichment was not observed. |
| Ownership classification | Dev Platform-owned |
| Maintenance-surface baseline (source / tests / docs lines) | 946 / 456 / 14: `project_context.py` 73 + 4, `project_evidence.py` 529 + 4, `repository_goal_scan.py` 332 + 4; their three test files; `docs/context/README.md`. |
| Retirement set (adopt) or retention evidence (keep) | An implicit provider call without the opt-in flag, auto-publishing to a shared default branch, a misleading success message, and an unignored output tree in the project root. |
| Projected maintenance reduction (adopt) | not applicable |

## Capability: dashboard and session, usage and friction analytics

| Field | Evidence |
| --- | --- |
| Decision | `reject-for-now` |
| Observed behavior and acceptance outcome | `teamai dashboard -p 37219` listened on `127.0.0.1` only and was stopped after the probe. Simulated hook events wrote the following to sandbox `~/.teamai`: `usage.jsonl` (`skill`, `timestamp`, `tool`) and `dashboard/events.jsonl` with `sessionId`, `cwd`, a `correction` flag and the **raw prompt text** as `promptSummary`. With `usageReport: false` no statistics were pushed. For one pull with `usageReport: true`, the CLI pushed `stats/<user>.yaml` to the team `teamai-reports` branch. It held skill use counts, session and intervention counts, prompt count, token and cost counters, and daily session outcomes; the prompt text was not pushed. Acceptance: it measures agent-session usage, not the revision-bound process health, rollout state or routing calibration that Dev Platform reports cover. |
| Lifecycle coupling | Negative. Data capture depends on machine-wide HOME hooks on every session, and team reporting is on by default and runs on every pull. |
| Migration cost | Not a substitute. Own reports would remain. |
| Release cadence and churn | Dashboard/analytics is beta per *desk research*. The shipped `[Unreleased]` notes change correction detection and reporting scope. |
| Security and privacy (what leaves the machine, command surfaces) | Local: raw prompt text is kept in `dashboard/events.jsonl`. Remote: aggregate statistics per user go to the team repository when `usageReport` is on (the default). The Stop hook set `lastUpdateCheck`, meaning it made an npm registry query, even with `updatePolicy: skip`. |
| Failure and rollback behavior | `events.jsonl`, including the prompt text, `usage.jsonl` and `votes/` survived `teamai uninstall`, as did the pushed `stats/` on the remote. |
| Codex / Claude compatibility | Hook dispatch is installed for both; only Claude-shaped payloads were simulated. Codex capture is unknown. |
| Ownership classification | Dev Platform-owned |
| Maintenance-surface baseline (source / tests / docs lines) | 1233 / 1002 / 61: health review (`notify_platform_health_review.py` 218, `publish_platform_health_review_report.py` 444, `private_platform_health_preflight.py` 80), `managed_project_status.py` 487 + 4; their four test files; `docs/private-platform-health-review.md`. Routing efficiency and calibration reports are inside `model_routing.py` and are counted under model profiles. |
| Retirement set (adopt) or retention evidence (keep) | Raw prompts retained after uninstall, per-user statistics pushed by default, and capture tied to machine-wide hooks. It also measures a different subject than the own reports. |
| Projected maintenance reduction (adopt) | not applicable |

## Capability: multi-project management, roles and namespaces

| Field | Evidence |
| --- | --- |
| Decision | `watch-only` |
| Observed behavior and acceptance outcome | The team repository declared roles `dev`/`ops` and projects `devplatform`/`managed`. The Dev Platform copy (`dev` + `devplatform`) received only the `alpha` namespace skills, and the `alpha/pilot-skill` override won over the root skill. The managed fixture (`ops` + `managed`) received only `beta-only`. Switching the managed fixture with `projects set` / `roles set` followed by `pull` added the new namespace skills and removed the old ones. With namespaces active, root-level skills were not synced at all. The member roster on `teamai-reports` recorded both projects. Acceptance: resource partitioning works. It is not a substitute for the managed-project registry or rollout, which deliver immutable Dev Platform releases through reviewed PRs. |
| Lifecycle coupling | Partitions ride the same mutable default branch. There is no per-project release pin or rollback target. |
| Migration cost | unknown for an additive role layer. Not applicable as a rollout replacement. |
| Release cadence and churn | The shipped `[Unreleased]` notes change agent namespaces and add role-scoped hooks and MCP; they also mention `.teamai` data-partition auto-migration. |
| Security and privacy (what leaves the machine, command surfaces) | The member roster (username, projects) is pushed to the team remote at `init`. |
| Failure and rollback behavior | Namespace switches cleaned up the previous namespace's skills. An uninstall in one project removed the other project's hooks (see shared resources). |
| Codex / Claude compatibility | Namespace filtering applied identically to `.claude` and `.codex`. |
| Ownership classification | Dev Platform-owned |
| Maintenance-surface baseline (source / tests / docs lines) | 3838 / 3271 / 308: `managed_projects.py` 210, the `rollout_*` scripts (1681 + 241 + 35 + 194 + 374 + 127 + 246), `shared_workspace.py` 725 + 5; the rollout, promotion and shared-workspace tests; `docs/managed-rollout.md`. |
| Retirement set (adopt) or retention evidence (keep) | The registry and rollout need immutable release references, PR-based controlled rollout and rollback. TeamAI projects are namespace filters over a mutable branch with a machine-wide uninstall. Roles have no Dev Platform counterpart, so an additive use stays under watch. |
| Projected maintenance reduction (adopt) | not applicable |

## Capability: model profiles

| Field | Evidence |
| --- | --- |
| Decision | `watch-only` |
| Observed behavior and acceptance outcome | Absent on stable. `teamai model` is an unknown command, there is no `models` subcommand, and the embedded `src/types.ts` has no model-profile schema; the only "model" key is `modelAliases` for cost estimation. Model profiles exist only in 0.26 betas, which are said to store API keys in plaintext files (mode 0600) written into agent settings (*desk research only*; roadmap evidence). |
| Lifecycle coupling | unknown |
| Migration cost | unknown |
| Release cadence and churn | Prerelease-only. |
| Security and privacy (what leaves the machine, command surfaces) | unknown on stable; the prerelease key handling is *desk research only*. |
| Failure and rollback behavior | unknown |
| Codex / Claude compatibility | unknown |
| Ownership classification | Dev Platform-owned |
| Maintenance-surface baseline (source / tests / docs lines) | 2986 / 1922 / 182: `model_routing.py` 2825 + 4 (includes the routing efficiency/calibration reports), `start_tier_routing.py` 157; `tests/test_model_routing.py`, `tests/test_start_tier_routing.py`; `docs/engineering/model-routing.md`. |
| Retirement set (adopt) or retention evidence (keep) | The capability is not in the stable release and cannot be adopted on prerelease evidence. `model_routing` is a recorded routing gate with provider tiers, which a model-profile file cannot stand in for. |
| Projected maintenance reduction (adopt) | not applicable |

## Boundary summary

| Area | Classification |
| --- | --- |
| Shared agent resources and distribution | Dev Platform-owned |
| Version-bound or on-demand skills | Dev Platform-owned |
| Learnings and recall | Dev Platform-owned |
| Codebase knowledge or wiki | Dev Platform-owned |
| Dashboard and analytics | Dev Platform-owned |
| Multi-project management, roles and namespaces | Dev Platform-owned |
| Model profiles | Dev Platform-owned |

No area is `adopt-next-step`. TeamAI is not a dependency of Dev Platform or of
rendered managed projects.

## Maintenance surface

Line counts were measured with `wc -l` at the evaluated revision. Each count
includes the `scripts/` shim where one exists.

| Area | Own files | Source / tests / docs lines | Retirement set or retention |
| --- | --- | --- | --- |
| Shared resources | `capability_manager.py`, `capability_evals.py`, `project_sync.py`; `test_capability_manager.py`; `engineering-capabilities.md` | 1133 / 763 / 342 | Retained: mutable pulls, surface collisions, hook opt-out bypass |
| Version-bound skills | Shares the shared-resources code; `release-policy.md` | shared / shared / 56 | Retained: absent on stable |
| Learnings and recall | `agent_friction.py`; `test_friction_review.py`; friction routing section | 1134 / 725 / 40 | Retained: unreviewed push, no issue routing |
| Codebase wiki | `project_context.py`, `project_evidence.py`, `repository_goal_scan.py`; three tests; `docs/context/README.md` | 946 / 456 / 14 | Retained: implicit provider call, auto-publish |
| Dashboard and analytics | health review scripts, `managed_project_status.py`; four tests; `private-platform-health-review.md` | 1233 / 1002 / 61 | Retained: prompt retention, default reporting, different subject |
| Roles and multi-project | `managed_projects.py`, `rollout_*`, `shared_workspace.py`; rollout, promotion and workspace tests; `managed-rollout.md` | 3838 / 3271 / 308 | Retained: no immutable release or rollback |
| Model profiles | `model_routing.py`, `start_tier_routing.py`; two tests; `model-routing.md` | 2986 / 1922 / 182 | Retained: absent on stable |

## Re-evaluation triggers

Re-evaluate when a stable TeamAI release meets any of the following:

- it offers a team-repository reference pin;
- it lets `init` honor `sharing.hooks.autoApply`;
- it protects foreign-owned skill names;
- it supports a project-scoped uninstall;
- it makes provider-free codebase extraction the default;
- it promotes version-bound skills or model profiles to stable.
