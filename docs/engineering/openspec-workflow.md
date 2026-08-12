# OpenSpec workflow (central repository)

Detailed OpenSpec guidance for `dev-platform` itself. `AGENTS.md` carries the always-on invariants; this document carries the mechanics.

## Contract model

Do not treat platform sources as one flat hierarchy:

- `AGENTS.md` — process and safety constraints for changing the platform.
- `openspec/specs/` — accepted platform behavior after archived changes.
- `openspec/changes/<active>/` — approved deltas currently changing that behavior.
- `template/` and platform code — implementation of current specs plus active deltas.
- `docs/` — durable architecture, adoption and operating guidance.

Do not create a second backlog for work represented by an active OpenSpec change.

## No silent divergence

For non-trivial platform changes, use OpenSpec before implementation. If implementation changes intent, behavior, design, or execution dependencies, update the corresponding artifact first:

- goal or scope changed -> `proposal.md`;
- observable behavior changed -> delta specs;
- technical approach changed -> `design.md`;
- implementation order/dependencies changed -> `tasks.md`.

Do not knowingly let code drift from the active contract, and do not implement a different contract with the intention of repairing the specification afterwards.

## Verify, archive, then publish

Before archiving a non-trivial platform change, run relevant tests plus semantic OpenSpec verification. Prefer `/opsx:verify` when the installed tool integration exposes it. If the current agent environment cannot invoke that workflow, perform and document the equivalent OpenSpec review across completeness, correctness, and coherence. Structural `openspec validate` is useful but is not a substitute for semantic verification or project-specific checks.

A platform change is not done merely because its task checkboxes are complete. After semantic verification succeeds and material findings are resolved:

1. record `OpenSpec-Verify: PASS` and `Verification-Method: <method>` in the active change's `verification.md`;
2. archive through the platform lifecycle helper;
3. commit the resulting current-spec/archive changes;
4. only then publish.

For the central repository, the lifecycle helper is invoked as:

```bash
python3 template/scripts/openspec_lifecycle.py archive <change>
```

Completed-but-active changes are treated as lifecycle debt and are blocked by platform CI.

Do not fabricate a verification receipt. The verification report must state what was actually checked and which method was used.

## OpenSpec dependency policy

OpenSpec is external; do not vendor generated Claude/Codex skills. `.dev-platform.toml` records minimum/tested CLI versions. The doctor may warn/fail on version compatibility but must not silently mutate a user's global OpenSpec installation.
