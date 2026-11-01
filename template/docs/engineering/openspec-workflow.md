# OpenSpec workflow

OpenSpec is the planning contract for non-trivial product and architecture changes. It complements repository process rules and project-specific verification.

## OpenSpec model used by Dev Platform

This section is sufficient to run the standard lifecycle without external OpenSpec documentation.

### Layout and artifact roles

- `openspec/specs/` holds the accepted current behavior, organized by capability.
- `openspec/changes/<change>/` holds one active change:
  - `proposal.md` states why, what changes, success evidence, constraints and non-goals.
  - `specs/<capability>/spec.md` is the delta spec: the observable behavior this change adds, modifies or removes.
  - `design.md` records the technical approach, decisions, risks and mitigations.
  - `tasks.md` is the ordered execution checklist.
  - `verification.md` is the truthful receipt of what was actually checked and how.
- `openspec/changes/archive/` holds completed changes. Archiving merges the delta into `openspec/specs/`.

Accepted specs describe what is true now; the active delta describes what is approved to become true. Target behavior is the two combined.

### Requirements and scenarios

A delta spec groups requirements under `## ADDED Requirements`, `## MODIFIED Requirements` and `## REMOVED Requirements`. Each requirement is a `### Requirement: <name>` with a normative statement using SHALL/MUST, followed by one or more scenarios:

```
#### Scenario: <name>

- **WHEN** <condition>
- **THEN** <observable result>
```

A modified requirement restates the full updated requirement. Scenarios must be concrete and verifiable.

### Changing the contract during implementation

When implementation shows the plan must change, update the owning artifact first, then continue: intent or scope in `proposal.md`, observable behavior in the delta specs, approach in `design.md`, order or dependencies in `tasks.md`. Never let code and artifacts knowingly disagree.

### Verify, archive, publish

1. Run project tests and checks.
2. Perform semantic verification: re-read the change and the implementation and assess completeness, correctness and coherence. This is distinct from structural validation (`openspec validate`), which checks only artifact format.
3. Record the result in `verification.md`, stating what was checked and by which method.
4. Commit the package (tasks, delta specs, `verification.md`); archive rejects uncommitted authored package files before review or checks.
5. Archive with `python3 scripts/openspec_lifecycle.py archive <change>`; verify hygiene with `python3 scripts/openspec_lifecycle.py check`.
6. Publish with `python3 scripts/finish_task.py`.

Managed tasks start with `python3 scripts/start_managed_task.py`. Check the installed OpenSpec version against the policy below with `python3 scripts/platform_doctor.py`.

### Upstream OpenSpec versus Dev Platform

Upstream OpenSpec documentation is supplementary reference only. Use the Dev Platform entrypoints above rather than the raw `openspec` CLI archive command, because they enforce lifecycle hygiene, receipts and publication rules that upstream does not.

## Contract model

Do not model these as a flat precedence ladder:

1. `AGENTS.md` constrains **how work may be performed**.
2. `openspec/specs/` states the **accepted current behavior**.
3. `openspec/changes/<active>/` states the **approved delta** currently changing that behavior.
4. Code implements current behavior plus approved active deltas.

The target behavior during an active change is therefore `current specs + active delta`, subject to process/safety constraints.

## No silent divergence

If implementation reveals that the plan must change, update the relevant artifact before proceeding in a different direction:

- intent/scope -> `proposal.md`;
- observable behavior -> delta specs;
- technical approach -> `design.md`;
- execution order/dependencies -> `tasks.md`.

Do not knowingly make code and OpenSpec disagree and plan to repair the docs later.

## Author the outcome contract

For non-trivial changes, make the expected outcome and concrete success criteria or verification evidence explicit in `proposal.md`. Use a quantitative threshold when it meaningfully measures the result; documentation, workflow, instruction, UX, and similar qualitative work may instead use binary or directly observable evidence. Do not invent a KPI merely to fill a section.

Right-size the change before committing to its artifacts. One OpenSpec change should have one intent that can be stated in a sentence. Apply a **split test**: if a substantial part could be accepted, delivered, verified, or rolled back independently while the remainder waits, split it into a separate change unless those parts are jointly required to produce one observable outcome. Touching several files, components, or capabilities is not by itself a reason to split when they are inseparable for that outcome.

State relevant constraints and non-goals to bound the accepted iteration. When a proposed change materially alters an existing workflow, UX, behavior, contract, or architecture path and the transition would otherwise be unclear, add a concise current-to-target description. Do not add an empty AS-IS/TO-BE section for a self-contained additive change.

In `design.md`, record concrete risks and mitigations when the work materially affects data or migrations, security/privacy, CI or release lifecycle, external integrations, backwards compatibility, cross-project rollout, or a comparable high-consequence boundary. Low-risk work does not need a ceremonial risk table.

Keep this context in the existing proposal, specs, design, and tasks artifacts. Do not create a mandatory `intent.md`, Must/Should/Could layer, or manual status/date/expiry/artifact ledger; lifecycle state and receipts already have authoritative sources.

### Carry Requirement binding levels into OpenSpec

When a change comes from a Business Requirement, each material point keeps the binding level the Requirement gave it. The three levels are defined in [section 4 of the requirement authoring standard](../../dev-platform/capabilities/requirement-authoring.md#4-make-binding-visible-in-plain-words). OpenSpec requirements describe the mandatory result and observable behavior; no point is bound more tightly in OpenSpec than it was in the Requirement.

- **Fixed**: write the value exactly (verbatim text, order, value or rule) and check it with a scenario.
- **Meaning fixed, execution variable**: write the meaning or the properties the user must be able to observe, and where they must be observable. Leave the presentation open. The scenario checks the property, not a widget.
- **Delegated**: do not raise the point into a requirement. The executor decides inside the accepted corridor; at most `design.md` records the choice.

An example, illustrative value or mockup informs the meaning, but it binds exactly only what the Requirement marked as fixed. Delegated presentation never relaxes financial, data, technical, security or accessibility constraints, rights or accepted scenarios. These rules apply to new authoring; accepted specs are not rewritten to follow them.

Worked example. A Requirement for a cash-flow report fixes three things: the report's breakdown switch offers "By item · By object · By activity" in that order, the side "Period totals" card is removed, and the page has no horizontal scrolling at 375 px. It also requires that the balances be shown with a note that they cover only known places, not all of the business's free money, and that places without a known balance get a warning; both must be visible next to the balances. The meaning is fixed, the presentation is delegated, and the mockup amounts are illustrative. In OpenSpec, the three fixed points become exact requirements, each with a scenario: the switch shows the three options in that order, the "Period totals" card does not appear, and the page at 375 px has no horizontal scrolling. The meaning becomes one requirement with a scenario that checks the user sees both statements next to the balances. The banner, caption or icon, wording beyond the agreed text, placement inside the strip and the mockup amounts appear in no requirement.

Wrong: "A yellow banner with an info icon SHALL be shown above the balances." This hardens a delegated presentation into an exact one that the Requirement never fixed.

Wrong: "A hint MAY be shown next to the balances." This weakens a fixed meaning: the Requirement makes the warning mandatory, so the OpenSpec requirement must not make it optional.

## Project-context routing

Use [the project context map](../context/README.md) only when an artifact reaches
project/domain knowledge that repository process and OpenSpec do not already
own. For a proposal, load the relevant product or domain context when scope
depends on goals, users, scenarios, terminology, or product invariants. For a
design, load focused architecture context and its linked canonical decision when
an invariant or prior decision matters. For tasks and implementation, load a
recorded anti-pattern or representative example when the scoped work intersects
it. Do not load the entire context pack or copy it into every artifact.

## Verify, archive, then publish

For non-trivial changes:

`plan review -> implementation -> project tests/QA -> semantic OpenSpec verify -> verification receipt -> archive -> publish`

Prefer `/opsx:verify` when the installed agent integration exposes it. If the current environment cannot invoke that workflow, OpenSpec allows the agent to re-read the change and implementation and perform the equivalent review. The equivalent review must cover the authored outcome and success evidence plus **completeness, correctness, and coherence**.

Semantic verification and `openspec validate` are different. The former checks implementation against intent; the latter checks OpenSpec structure. Neither replaces project-specific tests, E2E, browser/render QA, migrations or operational checks.

### Independent review evidence

For a material managed change, independent review is required when the
repository sets `[independent_review] enabled = true` (the central repository
does; the downstream template default stays `false`, so Copier updates do not
change a project until it opts in). Quick tasks without managed provenance are
never reviewed.

The platform launches the reviewer itself. Each of the two perspectives
(`spec-fidelity` and `engineering-quality`) runs as a fresh, non-resumable
process through a provider adapter:

- Codex: `codex exec --sandbox read-only --ephemeral` in the task worktree;
- Claude Code: headless print mode restricted to `Read,Grep,Glob` with
  `--permission-mode dontAsk`, `--no-session-persistence` and no MCP servers.

The reviewer provider defaults to the current task route's provider; setting
`[independent_review] provider = "codex"` or `"claude"` is the only way to
review across providers. The model comes from the `[model_routing]` profile
mapping (`[independent_review] profile`, default `standard`), and
`[independent_review] timeout_seconds` bounds each launch (default 1800). The
Claude binary resolves from the machine-local `DEV_PLATFORM_CLAUDE_BIN`
environment variable, then `claude` on `PATH`.

```bash
python3 scripts/independent_review.py preflight [<change>]
python3 scripts/independent_review.py run <change>
```

`preflight` proves the reviewer runtime is usable on this host and account
before any review perspective launches: it resolves the provider, the exact
selected model and the CLI binary, then sends one small headless probe with
that exact model through the same read-only adapter flags, under the same
workspace mutation postcheck, bounded by
`[independent_review] preflight_timeout_seconds` (default 120). It prints the
resolved provider, model and binary with `ready` and an actionable
`limitation`, exits non-zero when not ready, and writes no review evidence, so
run it right after routing a managed task and before implementation. A
missing binary, nonzero exit, error result or timeout names the CLI's own
bounded error and the next step: log the CLI in, point
`DEV_PLATFORM_CLAUDE_BIN` at the Claude Code CLI, or change the
`[model_routing]` / `[independent_review]` binding for this account. No other
model or provider is ever tried. `run` (and therefore archive) performs the
same preflight first; when it fails, both perspectives are recorded as
`unavailable` with that limitation and no perspective is launched.

`run` prepares (or reuses a current) provider-neutral review request, builds
each prompt only from that request plus a precomputed candidate diff in a
temporary directory outside the repository, and requires structured findings
(`id`, `severity: material|advisory`, `summary`, `evidence`). Prompts, stdout
and stderr are not persisted. Each report records platform-observed launch
evidence, the enforced read-only mechanism, the selected model and a digest of
the raw output. A content snapshot of the task worktree and the integration
checkout before and after each launch proves read-only execution; any mutation,
missing binary, nonzero exit, timeout or malformed output produces an
`unavailable` report with an actionable limitation, and the platform never
repairs or cleans a mutation. A hand-written report
(`scripts/independent_review.py record`, kept for compatibility) does not
satisfy a required review.

Evidence binds to the candidate's task-content identity, excluding only the
change's `verification.md`, `evidence/`, `automated-checks.json`, review
request/reports/dispositions and the `openspec/specs/` paths archive
materializes from the change's own delta specs. Archive bookkeeping and a clean
main merge that touches no task path therefore keep evidence valid; any other
task change makes it stale and requires a fresh review.

The reviewer context is the same set: the candidate diff covers only the
changed paths that identity binds (passed as literal pathspecs), so committed
lifecycle evidence — earlier review requests, reports and dispositions,
automated checks, the verification receipt, `evidence/` and archive-derived
spec materialization — is never presented as candidate content. The request
records the withheld paths as `excluded_lifecycle_paths`, and the prompt tells
the reviewer they are lifecycle evidence that must not be reported as
findings. An unchanged final candidate therefore needs exactly one review
round across archive, evidence commits and finish.

Reviewer reports are immutable. A material finding blocks until it is fixed
(commit the fix and rerun the review) or rejected with a rationale in the
separate disposition record, bound to the exact report digest:

```bash
python3 scripts/independent_review.py dispose <change> --perspective <perspective> --finding <id> --status rejected --rationale "<why>"
```

`--status blocker` records a retained blocker. An unavailable perspective, a
blocker, or a material finding without a current rejection blocks archive and
publication rather than letting passing deterministic tests claim independent
verification.

When review is required, archive never runs it: the queue review job (or,
without a queue, `finish`) runs a missing, stale or unavailable review, and
archive only requires its evidence. Archive evaluates every precondition
(tasks, receipt, review evidence, routing, automated-check evidence, committed
package, private lineage, checkout identity) before any archive work and fails
once listing each unmet one with its fix. `finish` re-validates the evidence
against the current task content before any publication step. Task status
(`finish_task.py --status`) and Requirement
`advance` report the derived `independent_review` state (`not-required`,
`missing`, `stale`, `blocked`, `ready`) and next command from the files in the
change directory, so a new Codex or Claude Code session can resume. Inspect or
check it directly with `python3 scripts/independent_review.py status <change>`
or `check <change>`. The corresponding `verification.md` must cite
`Independent-Review-Evidence: independent-review-request.json` alongside its
PASS receipt.

When a verification check fails, classify the failure relative to the authoritative base as `introduced`, `pre-existing`, or `unknown`. Claim `pre-existing` only when reproducible baseline evidence or another trustworthy unchanged-base signal proves it; missing evidence remains `unknown`, not a guess. A pre-existing failure does not excuse new regressions: report the baseline condition separately from failures introduced by the current change.

After material semantic findings are resolved, record the result in the active change's `verification.md` with:

```text
OpenSpec-Verify: PASS
Verification-Method: <method actually used>
```

The report should state what was checked and any warnings/suggestions that remain. For a platform-owned harness, the verification receipt must also contain:

```text
Automated-Checks-Evidence: automated-checks.json
```

Archive preflight checks this exact marker before it runs selected checks or writes evidence, so a missing receipt is actionable before archive mutation. The archive helper creates that file from the selected commands it actually runs, then refuses to archive if the selection is empty/invalid, any command fails, or the receipt does not cite the generated evidence. Add the marker only when the generated evidence will truthfully name the checks the helper ran. This is intentionally not required for `harness_mode=project`, where repository CI remains the product-verification authority.

Then archive through the platform entrypoint:

```bash
python3 scripts/openspec_lifecycle.py archive <change>
```

The helper requires all tasks to be complete, the PASS receipt plus method, a committed package and an authored `## Purpose` in every delta that creates a capability absent from `openspec/specs` (a missing, empty or `TBD`/`TODO`/`FIXME` Purpose is rejected before any mutation, because OpenSpec otherwise writes a placeholder Purpose that strict validation rejects). It runs strict validation, rehearses the archive and `validate --all --strict` on a disposable copy of `openspec/`, then invokes the OpenSpec CLI archive and validates the resulting OpenSpec state. If the real archive or its post-validation still fails, it restores the exact pre-archive `openspec/` tree and reports the failing items, so the same command can be rerun after the fix. It does not emulate semantic verification and does not install or upgrade OpenSpec.

`finish_task.py` and CI run lifecycle hygiene. If all task checkboxes in an active change are complete but the change is still active, publication is blocked. This turns “remember to archive” into a repository invariant rather than a human reminder.

While `archive <change>` runs the mandatory selected or protected checks, the hygiene check inside them (`openspec_lifecycle.py check`, which stays in the check groups) exempts exactly that archive target, so a verified change does not deadlock on its own archive. The helper validates the target (a valid name of an existing, completed active change) before any state changes and passes it only through the reserved `DEV_PLATFORM_ARCHIVE_TARGET` and `DEV_PLATFORM_ARCHIVE_ROOT` (the archiving checkout's real path) variables in the environment of that single validation subprocess. Hygiene applies the exemption only in that checkout: a context issued for a different checkout is ignored and the ordinary check runs (scoping, not a masked failure), exactly one variable of the pair set, an empty value, or a relative root path fails explicitly, and a pair for this checkout whose target is not a completed active change fails explicitly. Any other completed-but-active change still blocks, and nothing persists after a failed archive: the next ordinary `check` blocks again. Do not export these variables by hand.

Where `/opsx:verify` is the selected method, the expanded OpenSpec verify workflow must be enabled for the repository (`openspec config profile`, then `openspec update`). `platform_doctor.py` detects whether that generated workflow is present, but absence is not a reason to skip semantic verification: use the documented equivalent review if the current agent surface cannot invoke it.

## OpenSpec version policy

`.dev-platform.toml` records the platform-tested OpenSpec version and minimum compatible version. `platform_doctor.py` warns when the local CLI is newer than the tested version and fails when it is below the minimum. The platform does not silently upgrade a user's global CLI.
