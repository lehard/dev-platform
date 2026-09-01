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

Right-size the change before committing to its artifacts. One OpenSpec change should have one intent that can be stated in a sentence. Apply a **split test**: if a substantial part could be accepted, delivered, verified, or rolled back independently while the remainder waits, split it into a separate change unless those parts are jointly required to produce one observable outcome. Touching several files, components, or capabilities is not by itself a reason to split when they are inseparable for that outcome.

State relevant constraints and non-goals to bound the accepted iteration. When a proposed change materially alters an existing workflow, UX, behavior, contract, or architecture path and the transition would otherwise be unclear, add a concise current-to-target description. Do not add an empty AS-IS/TO-BE section for a self-contained additive change.

In `design.md`, record concrete risks and mitigations when the work materially affects data or migrations, security/privacy, CI or release lifecycle, external integrations, backwards compatibility, cross-project rollout, or a comparable high-consequence boundary. Low-risk work does not need a ceremonial risk table.

Keep this context in the existing proposal, specs, design, and tasks artifacts. Do not create a mandatory `intent.md`, Must/Should/Could layer, or manual status/date/expiry/artifact ledger; lifecycle state and receipts already have authoritative sources.

## Verify, archive, then publish

Before archiving a non-trivial platform change, run relevant tests plus semantic OpenSpec verification. Prefer `/opsx:verify` when the installed tool integration exposes it. If the current agent environment cannot invoke that workflow, perform and document the equivalent OpenSpec review across the authored outcome and success evidence, completeness, correctness, and coherence. Structural `openspec validate` is useful but is not a substitute for semantic verification or project-specific checks.

### Independent review evidence

For a material managed change, a repository may opt into independent review with
`[independent_review] enabled = true`. Prepare a provider-neutral review
request against the exact committed candidate before asking an independently
started, read-only runtime to review it:

```bash
python3 scripts/independent_review.py prepare <change> --base origin/main
```

The request binds two reports (`spec-fidelity` and `engineering-quality`) to
the base SHA, candidate SHA and binary diff hash. The runtime records each
report with `scripts/independent_review.py record <change> --report <path>`;
it must identify its fresh context, attest to no write access, and report a
limitation rather than invent findings if review was unavailable.
The platform intentionally does not launch a provider: the generated request
is the replaceable runtime integration, and report validation is the lifecycle
boundary. Review execution is evidence-only and must not publish code, mutate
Backlog/Project state, archive, or set completion state.

Before PASS/archive, check the reports with:

```bash
python3 scripts/independent_review.py check <change>
```

When enabled, archive readiness requires both current reports. A candidate
change invalidates old evidence. A material finding must be fixed or explicitly
rejected with rationale; a blocker, missing disposition, or unavailable report
blocks the archive rather than letting passing deterministic tests claim
independent verification. The corresponding `verification.md` must cite
`Independent-Review-Evidence: independent-review-request.json` alongside its
PASS receipt. The capability is opt-in so quick or bounded work is not forced
into a heavy review by default.

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
