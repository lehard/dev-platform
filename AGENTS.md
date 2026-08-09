# Developer Platform Agent Rules

This repository is the central source of truth for reusable engineering process shared by multiple software projects. Treat changes here as potentially cross-project.

## Contract model

Do not treat platform sources as one flat hierarchy:

- `AGENTS.md` — process and safety constraints for changing the platform.
- `openspec/specs/` — accepted platform behavior after archived changes.
- `openspec/changes/<active>/` — approved deltas currently changing that behavior.
- `template/` and platform code — implementation of current specs plus active deltas.
- `docs/` — durable architecture, adoption and operating guidance.

Do not create a second backlog for work represented by an active OpenSpec change.

## No silent divergence

For non-trivial platform changes, use OpenSpec before implementation. If implementation changes intent, behavior, design, or execution dependencies, update the corresponding proposal/spec/design/tasks artifact first. Do not knowingly let code drift from the active contract.

Before archiving a non-trivial platform change, run relevant tests plus semantic OpenSpec verification. Prefer `/opsx:verify` when the installed tool integration exposes it. If the current agent environment cannot invoke that workflow, perform and document the equivalent OpenSpec review across completeness, correctness, and coherence. Structural `openspec validate` is useful but is not a substitute for semantic verification or project-specific checks.

A platform change is not done merely because its task checkboxes are complete. After semantic verification succeeds and material findings are resolved, record `OpenSpec-Verify: PASS` and `Verification-Method: <method>` in the active change's `verification.md`, archive through the platform lifecycle helper, commit the resulting current-spec/archive changes, and only then publish. Completed-but-active changes are treated as lifecycle debt and are blocked by platform CI.

For the central repository, the lifecycle helper is invoked as:

```bash
python3 template/scripts/openspec_lifecycle.py archive <change>
```

Do not fabricate a verification receipt. The verification report must state what was actually checked and which method was used.

## Scope discipline

Promote a rule/tool only when it is reusable across projects or a defined workflow profile. Keep application-domain rules, credentials, machine-local paths and one-off workarounds in the owning project.

A change to a downstream managed file must consider both new-project rendering and Copier update behavior for existing projects.

## Platform capabilities

The shared lifecycle is composable. `light`, `standard`, and `multi-agent` profiles select capabilities rather than forking the template. GitHub sync/publish, checks, OpenSpec policy and release pinning are core; worktrees/board are multi-agent capabilities.

## Release safety

Downstream reusable CI must never reference `dev-platform@main`. It must use a versioned release ref (or immutable SHA). Release refs are append-only and must never be moved after publication. Platform upgrades reach projects through reviewed Copier update PRs.

`managed-projects.json` is the explicit cross-repository rollout allowlist. Automation must write only to entries whose state is `managed`; `candidate` is non-mutating documentation until reviewed adoption is complete. Exact-version rollout must target an immutable SemVer tag, fail closed on conflicts/ownership ambiguity, never force-push, and never auto-merge by default.

Cross-repository rollout credentials must come from the dedicated least-privilege GitHub App. Never commit its private key, installation token or a fallback personal access token.

## Validation

At minimum:

```bash
python3 -m compileall -q template/scripts scripts
python3 scripts/managed_projects.py validate
python3 -m unittest discover -s tests -v
python3 template/scripts/openspec_lifecycle.py check
```

When Copier is available, render the template and compile/run the generated doctor. For Git lifecycle changes, exercise temporary local/bare remotes so fetch/sync/direct-publish safety is tested.

## OpenSpec dependency policy

OpenSpec is external; do not vendor generated Claude/Codex skills. `.dev-platform.toml` records minimum/tested CLI versions. The doctor may warn/fail on version compatibility but must not silently mutate a user's global OpenSpec installation.

## Friction promotion

Local friction stays machine-local by default. Promotion to the central inbox is an explicit sanitized action; raw evidence is not uploaded automatically. Multiple observations should be reviewed before turning a candidate into a permanent platform rule.
