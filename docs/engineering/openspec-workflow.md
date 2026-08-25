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

## Author the outcome contract

For non-trivial changes, make the expected outcome and concrete success criteria or verification evidence explicit in `proposal.md`. Use a quantitative threshold when it meaningfully measures the result; documentation, workflow, instruction, UX, and similar qualitative work may instead use binary or directly observable evidence. Do not invent a KPI merely to fill a section.

State relevant constraints and non-goals to bound the accepted iteration. When a proposed change materially alters an existing workflow, UX, behavior, contract, or architecture path and the transition would otherwise be unclear, add a concise current-to-target description. Do not add an empty AS-IS/TO-BE section for a self-contained additive change.

In `design.md`, record concrete risks and mitigations when the work materially affects data or migrations, security/privacy, CI or release lifecycle, external integrations, backwards compatibility, cross-project rollout, or a comparable high-consequence boundary. Low-risk work does not need a ceremonial risk table.

Keep this context in the existing proposal, specs, design, and tasks artifacts. Do not create a mandatory `intent.md`, Must/Should/Could layer, or manual status/date/expiry/artifact ledger; lifecycle state and receipts already have authoritative sources.

## Verify, archive, then publish

Before archiving a non-trivial platform change, run relevant tests plus semantic OpenSpec verification. Prefer `/opsx:verify` when the installed tool integration exposes it. If the current agent environment cannot invoke that workflow, perform and document the equivalent OpenSpec review across the authored outcome and success evidence, completeness, correctness, and coherence. Structural `openspec validate` is useful but is not a substitute for semantic verification or project-specific checks.

When a verification check fails, classify the failure relative to the authoritative base as `introduced`, `pre-existing`, or `unknown`. Claim `pre-existing` only when reproducible baseline evidence or another trustworthy unchanged-base signal proves it; missing evidence remains `unknown`, not a guess. A pre-existing failure does not excuse new regressions: the verification report must distinguish the baseline condition from failures introduced by the current change.

A platform change is not done merely because its task checkboxes are complete. After semantic verification succeeds and material findings are resolved:

1. record `OpenSpec-Verify: PASS` and `Verification-Method: <method>` in the active change's `verification.md`;
2. archive through the platform lifecycle helper;
3. commit the resulting current-spec/archive changes;
4. only then publish.

For a platform-owned harness, the verification receipt must also contain:

```text
Automated-Checks-Evidence: automated-checks.json
```

Archive preflight checks this exact marker before it runs selected checks or writes evidence, so a missing receipt is actionable before archive mutation. Add the marker only when the generated evidence will truthfully name the checks the helper ran. This requirement does not apply to `harness_mode=project`, where repository CI remains the product-verification authority.

For the central repository, the lifecycle helper is invoked as:

```bash
python3 template/scripts/openspec_lifecycle.py archive <change>
```

Completed-but-active changes are treated as lifecycle debt and are blocked by platform CI.

Do not fabricate a verification receipt. The verification report must state what was actually checked and which method was used.

## OpenSpec dependency policy

OpenSpec is external; do not vendor generated Claude/Codex skills. `.dev-platform.toml` records minimum/tested CLI versions. The doctor may warn/fail on version compatibility but must not silently mutate a user's global OpenSpec installation.
