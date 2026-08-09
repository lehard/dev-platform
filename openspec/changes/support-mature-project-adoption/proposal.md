# Support mature project adoption

## Why

The current one-command adoption flow correctly distinguishes fresh repositories from existing ones, but it still assumes that every existing repository should adopt the platform-owned Git/task/check harness. That is unsafe for mature projects that already have a proven repository-specific lifecycle.

`Jara_Fin` exposes the gap clearly: it already owns multi-agent worktrees, an agent board, serialized merge/publish behavior, project-specific test selection, CI dependency setup and OpenSpec rules. The current existing-project defaults (`standard + harness_mode=platform + publish_mode=pr`) would layer a second lifecycle over that system. Adoption validation also calls the platform `select_checks.py` CLI contract (`--execute` / `--full`) even when the target repository owns a different selector, and generated platform CI can duplicate product CI without installing the project's dependencies.

The platform already has the `harness_mode=project` concept. Adoption and downstream CI need to honor it end-to-end.

## What changes

- Make first-time adoption choose repository kind and harness ownership as separate decisions.
- Detect mature project-owned lifecycle markers conservatively and preserve the existing project harness instead of overwriting it.
- Detect `multi-agent` when the existing repository already has worktree/agent-board coordination; otherwise retain the safest compatible workflow profile.
- Keep the one-command human interface: the human still provides only `owner/name`; internal migration settings are derived by the platform.
- Split adoption validation into platform/OpenSpec hygiene versus project-owned product checks.
- For `harness_mode=project`, stop requiring the target project's `select_checks.py` to implement the platform CLI and stop executing duplicate product checks from generated Dev Platform CI.
- Preserve existing project CI as the owner of dependency installation and application test execution.
- Make mature-repository path collisions reviewable rather than destructive or a normal `.rej` failure mode.
- Add regression fixtures and an acceptance scenario representing a Jara_Fin-like mature multi-agent repository.

## Non-goals

- Do not copy Jara_Fin-specific scripts or domain rules into the shared template.
- Do not replace or normalize a mature repository's proven agent board, worktree, merge, publish or test-selection implementation merely to match platform defaults.
- Do not auto-merge existing-project adoption PRs.
- Do not automatically rewrite arbitrary project documentation or OpenSpec semantics.
- Do not weaken platform/OpenSpec lifecycle hygiene for project-owned harnesses.

## Scope

This change affects first-time adoption planning, Copier migration behavior for existing projects, downstream Dev Platform CI ownership, platform validation and adoption documentation. Fresh-project behavior and ordinary reviewed managed rollout should remain unchanged unless needed for compatibility.