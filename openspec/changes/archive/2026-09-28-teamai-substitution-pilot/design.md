## Sandbox

- Create a disposable directory outside every worktree. Set `HOME` and `npm_config_prefix` to paths inside it.
- Install exactly `teamai-cli@<stable>` from the public npm registry. This is the only network fetch; it is a third-party download and needs explicit operator permission at execution time.
- Configure `updatePolicy: skip` / `autoUpdate: false`, `sharing.env.injectShellProfile: false`, `usageReport: false`, and `sharing.hooks.autoApply: false` / `sharing.mcp.autoApply: false`. Leave `scripts.postPull` unset.
- Use a local bare Git repository with the generic git provider as the team repo. Use no tokens or real accounts.
- Capture sandbox file-system diffs before and after each scenario, so writes outside the declared targets are observed rather than assumed.
- Delete the sandbox after the evidence is recorded.

## Scenarios

1. **Dev Platform workflow:** a copy of this repository at the evaluated revision inside the sandbox, with Claude Code and Codex project surfaces. Observe how TeamAI resource sync interacts with `AGENTS.md`/`CLAUDE.md`, capability-generated `.claude/.codex` skills, and OpenSpec-generated skills (drift, overwrite, marker blocks).
2. **Managed project:** a project freshly rendered from the current template (standard profile, Claude and Codex), then run `capability_manager.py sync` and the platform doctor. Check whether TeamAI-distributed resources coexist with, replace, or conflict with platform-owned surfaces and pass the doctor.
3. **Per-area probes:**
   - pinning a resource revision;
   - on-demand/version-bound skill behavior on the stable release;
   - learnings write and recall;
   - codebase wiki extraction on this repository;
   - dashboard/analytics data capture and what would leave the machine;
   - roles/namespaces for two projects;
   - model profiles (expected unavailable on stable; record it as roadmap only).
4. **Failure and rollback:** remove TeamAI and verify the project returns to its pre-pilot state. Observe self-update and downgrade behavior with the version pinned.

## Decision and measurement

For each area, record the decision, observed evidence, coupling, migration cost, cadence and churn, security/privacy, rollback, Codex/Claude compatibility, and the ownership classification.

Use the maintenance-surface baseline measured at authoring as the starting point, re-measured at the evaluated revision. The source/tests line counts at authoring were:

- capability_manager 541/763; capability_evals 540/0;
- agent_friction 1134/0;
- project_context 77/128; project_evidence 533/197;
- model_routing 2585/1711;
- health review scripts about 742/711;
- managed_project_status 491/291.

The docs line counts are measured during the pilot.

## Spec

The spec delta states the post-pilot boundary independent of outcome: a decision exists for every area, and no area is TeamAI-owned until an adoption change lands. If the pilot surfaces a material contract conflict, stop and return it to the Requirement owner.
