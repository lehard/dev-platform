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

## Project-context routing

Use [the project context map](../context/README.md) only when an artifact reaches project/domain knowledge that repository process and OpenSpec do not already own. For a proposal, load the relevant product or domain context when scope depends on goals, users, scenarios, terminology, or product invariants. For a design, load focused architecture context and its linked canonical decision when an invariant or prior decision matters. For tasks and implementation, load a recorded anti-pattern or representative example when the scoped work intersects it. Do not load the entire context pack or copy it into every artifact.

## Verify, archive, then publish

Before archiving a non-trivial platform change, run relevant tests plus semantic OpenSpec verification. Prefer `/opsx:verify` when the installed tool integration exposes it. If the current agent environment cannot invoke that workflow, perform and document the equivalent OpenSpec review across the authored outcome and success evidence, completeness, correctness, and coherence. Structural `openspec validate` is useful but is not a substitute for semantic verification or project-specific checks.

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
`[model_routing]` / `[independent_review]` binding for this account. No other model or provider is tried unless `[independent_review] providers = ["codex", "claude"]` explicitly declares that ordered fallback. Only listed providers are probed; reports retain requested provider, executed provider and fallback reason. If all are unavailable, coordinator candidates become `blocked-retryable` with a fresh review job. `run` (and therefore archive) performs the
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

When review is required, the archive helper runs a missing, stale or
unavailable review automatically after its cheap deterministic checks and
before expensive validation, then stops with the findings and the exact next
commands if the evidence does not validate. `finish` re-validates the evidence
against the current task content before any publication step. Task status
(`dogfood_task.py status` / `finish_task.py --status`) and Requirement
`advance` report the derived `independent_review` state (`not-required`,
`missing`, `stale`, `blocked`, `ready`) and next command from the files in the
change directory, so a new Codex or Claude Code session can resume. Inspect or
check it directly with `python3 scripts/independent_review.py status <change>`
or `check <change>`. The corresponding `verification.md` must cite
`Independent-Review-Evidence: independent-review-request.json` alongside its
PASS receipt.

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

While `archive <change>` runs the mandatory selected or protected checks, the hygiene check inside them (`openspec_lifecycle.py check`, which stays in the check groups) exempts exactly that archive target, so a verified change does not deadlock on its own archive. The helper validates the target (a valid name of an existing, completed active change) before any state changes and passes it only through the reserved `DEV_PLATFORM_ARCHIVE_TARGET` and `DEV_PLATFORM_ARCHIVE_ROOT` (the archiving checkout's real path) variables in the environment of that single validation subprocess. Hygiene applies the exemption only in that checkout: a context issued for a different checkout is ignored and the ordinary check runs (scoping, not a masked failure), exactly one variable of the pair set, an empty value, or a relative root path fails explicitly, and a pair for this checkout whose target is not a completed active change fails explicitly. Any other completed-but-active change still blocks, and nothing persists after a failed archive: the next ordinary `check` blocks again. Do not export these variables by hand.

When `[private_lineage] enabled = true`, `archive <change>` first runs the existing `scripts/check_private_backlog_refs.py` over the current candidate, before review, selected checks, evidence writes or any OpenSpec mutation; the shared Requirement publisher runs the same gate before full candidate validation, including draft candidates. A private Issue reference in a child proposal, design or archived artifact therefore fails at the child archive with the guard's opaque diagnostic, and a missing guard fails explicitly with no substitute scanner. Publication keeps its own recheck. Checkouts without `private_lineage` are unchanged.

Do not fabricate a verification receipt. The verification report must state what was actually checked and which method was used.

## OpenSpec dependency policy

OpenSpec is external; do not vendor generated Claude/Codex skills. `.dev-platform.toml` records minimum/tested CLI versions. The doctor may warn/fail on version compatibility but must not silently mutate a user's global OpenSpec installation.

Coordinator-managed source candidates publish their active change at developer
handoff before independent review or archive. Review/repair jobs use the shared
candidate records and worker harness; passing review hands off as
`finalize-pending`. Archive validates existing review evidence instead of
launching a reviewer for these candidates. Selected-check evidence records the
same lifecycle-excluding task-content proof as review and is reused during
archive when unchanged. Missing or changed proofs fail closed. Required-check
gates also carry candidate identity; GitHub protected merge still requires its
own exact-head checks. A `finalize` job (`post_review_finalization.py`) then runs
`openspec_lifecycle.py archive <change> --finalize` in a disposable checkout,
reusing the review and selected-check evidence for the unchanged task-content
identity, and the candidate becomes `ready`; a later task-content change returns
it to review. When selected checks must be re-established because a review repair
changed the task content, the finalize job runs the real selected checks under the
bounded `select_checks.py --proven-base <sha>` contract, where `<sha>` is the
task-content base of the identity it proved equivalent to the recorded one, instead
of requiring the head to contain current `main`; the harness-executed evidence
records that contract and base. Finalization never fetches or merges `main`: base
actualization, the clean merge of current `main`, required CI on the merged head and
integration repair belong to the integration contour (see
[agent-workflow.md](agent-workflow.md#candidate-and-integration-contours)). A developer
re-admission of a descendant head with unchanged task content keeps the passed review,
so the review job completes without launching a reviewer. A completed-but-active change is blocked at integration admission
and merge (`openspec_lifecycle.py check --stage integration`, strict on `main`
and for non-coordinator finish), not at PR publication. When main changed only
the archive-derived current-spec paths of the candidate's own capabilities, the
coordinator re-derives them by replaying the archived deltas on main; this is
bookkeeping, required checks still run, and a failed replay is integration
repair. This handoff does not claim terminal delivery.
