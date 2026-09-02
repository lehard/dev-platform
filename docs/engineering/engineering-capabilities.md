# Optional engineering capabilities

Optional engineering capabilities are reusable development behaviors that compose with, rather than rename, `light`, `standard`, and `multi-agent` workflow profiles. They never add application runtime dependencies, production credentials, origin permissions, or write authority.

## Source and selection

Each descriptor in `dev-platform/capabilities/<id>.toml` is the provider-neutral source of truth. It declares identity, purpose, kind, invocation/visibility intent, ownership, provenance hash, safety boundary, dependencies and lifecycle policy. The referenced instruction file is hash-checked; external content must be pinned and is never fetched from a mutable upstream at runtime.

`dev-platform/capabilities.toml` is project-owned opt-in state. An empty `enabled` list means no provider skill surface, extra agent context, tool runtime, or dependency is materialized. Copier delivers the default file once and preserves later project choices.

## Lifecycle

Use the discoverable management entrypoint:

```bash
python3 scripts/capability_manager.py list
python3 scripts/capability_manager.py enable <id>
python3 scripts/capability_manager.py update <id> --change-kind material
python3 scripts/capability_manager.py audit
python3 scripts/capability_manager.py evaluate capability-catalog --fixture dev-platform/evals/capability-catalog-pilot.json --runtime fixture
```

It also exposes `create`, `remove`, `show`, `validate`, `sync`, and `eval-decision`. `create` accepts a reviewed descriptor plus sibling instruction file in the Dev Platform source through a managed task; downstream projects may only choose released descriptors. `remove` disables a capability and removes only its marked derived files. The current adapters materialize `auto+explicit` instruction-only and isolated tool-backed capabilities as native skill Markdown for Claude and Codex. Unsupported invocation intents are reported truthfully rather than emulated by a second router.

Capability authoring always performs structural validation and delegates its eval decision to `scripts/capability_evals.py`, which is the #79 provider-neutral eval core. Metadata-only changes are `skip-with-reason`; new, material, trigger, behavior, tool, and safety changes are `blocked/unavailable` until a supported live provider adapter is configured. A bounded deterministic fixture can instead produce `run`; this is for reproducible CI evidence, not a claim about a model provider's live triggering. `capability_manager.py evaluate` is the direct explicit-eval path for an existing capability.

## Provider-neutral evals

The eval core consumes a capability id from the existing descriptor lifecycle; it does not create a skill registry, provider materialization store, daemon, or task orchestrator. Its canonical report contains a candidate id, expectation, sample size, status distribution, prompt digest, bounded adapter provenance, and optional objective baseline/candidate outcomes. It never writes a transcript, prompt text, secret, or chain-of-thought into a report.

Run a bounded deterministic pilot with ten positive and ten hard-negative synthetic prompts, three samples each:

```bash
python3 scripts/capability_evals.py --json run \
  --fixture dev-platform/evals/capability-catalog-pilot.json \
  --runtime fixture --runs 3
```

The included objective comparison verifies the capability lifecycle's observable result: an opt-out project has no derived skill surface, while a selected canonical descriptor produces its marked provider surface. The fixture report labels this as `deterministic-fixture`; it is not live Codex or Claude evidence.

Current Codex and Claude adapters intentionally return `unsupported` rather than launch nested CLIs or infer a trigger from provider-specific stream events. That preserves the existing single-writer routing and containment contracts. A future adapter may be added only when its runtime offers truthful, supported trigger evidence; timeouts and runtime failures must remain distinct from `not-triggered`.

## Architecture Health Review

`architecture-health-review` is an opt-in, instruction-only advisory capability. Enable it only when a repository wants a bounded architecture evidence surface:

```bash
python3 scripts/capability_manager.py enable architecture-health-review
python3 scripts/capability_manager.py evaluate architecture-health-review --fixture dev-platform/evals/architecture-health-review-pilot.json --runtime fixture
```

The review is bound to a full revision, a declared path/question scope, and the evidence consulted. It considers interface depth, locality, coupling, leakage across boundaries, seams/adapters, and repeated abstractions, but deliberately has no universal score. Its report keeps observations, evidence, uncertainty/counter-evidence, and advisory improvements separate. A healthy control is required where a heuristic could otherwise over-report a smell.

It cannot change code, create commits, Issues, Backlog items, or managed tasks, or publish a report. A human who accepts a candidate promotes it separately through the normal Discuss/Backlog/OpenSpec task-intake lifecycle. Alternative-design analysis is available only for an explicitly marked high-consequence trigger; it compares at least two materially different options as evidence for the current human/OpenSpec decision and never selects or implements one.

### Upstream architecture-skill review

On 2026-09-02, the independently reviewed references were Matt Pocock's [`codebase-design`](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/engineering/codebase-design/SKILL.md) and [`improve-codebase-architecture`](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/engineering/improve-codebase-architecture/SKILL.md), both at commit `6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`. They are reference-only: Dev Platform vendors none of their files, fetches none at review time, and does not treat either as a workflow authority.

| Reusable heuristic | Dev Platform treatment |
| --- | --- |
| Small caller-facing interface, leverage, locality, and the deletion test | Adapt as evidence lenses; require callers/tests or other concrete evidence before an advisory candidate. |
| Scope a survey to a named concern or recent change hotspot | Adapt as a bounded-review rule; do not scan a repository by default. |
| One adapter is a hypothesis; genuinely varying adapters make a seam stronger | Adapt as counter-evidence against speculative indirection. |
| Shared design vocabulary | Adapt only where it clarifies an observation; Dev Platform preserves its own established terms, including boundary, rather than imposing a foreign glossary. |
| HTML report, automatic sub-agent exploration, inline documentation/ADR updates, Issue creation, and a grilling loop | Reject. The capability must remain repository- and backlog-read-only, with no second task state machine or provider-specific orchestration. |
| Parallel `design-it-twice` exploration | Adapt narrowly: a human must explicitly name a high-consequence trigger; the report compares at least two alternatives and remains evidence for the current decision. |

## Anthropic skill-creator review

The reviewed upstream is [`anthropics/skills`](https://github.com/anthropics/skills) commit `53048666b05b4799081517d00e09e0a2dd688678`, under `skills/skill-creator/`. Its `LICENSE.txt` is Apache-2.0. Dev Platform vendors none of its files; the pin and component map are review provenance for the independent implementation below.

| Upstream component | Dev Platform treatment | Reason |
| --- | --- | --- |
| `SKILL.md` authoring UX | Adapt | Generic create/update/audit intent remains discoverable through capability management; test effort is selected by workflow rather than a remembered lab command. |
| `quick_validate.py` | Adapt | Existing descriptor/hash validation is the deterministic structural check for every candidate. |
| `aggregate_benchmark.py` / `generate_report.py` | Adapt | `capability_evals.py` aggregates sample sizes, rates and status distributions in a provider-neutral JSON report. |
| `package_skill.py` | Reject | Existing canonical descriptors and marked derived surfaces already provide controlled materialization. |
| `improve_description.py` | Reference-only | It invokes a nested provider CLI and retains prompt/response material, which is outside the bounded evidence policy. |
| `run_eval.py` / `run_loop.py` | Reject as platform core | They create temporary `.claude/commands`, invoke nested `claude -p`, and depend on Claude `Skill`/`Read` stream events. |
| evaluator agents and HTML viewer | Reference-only | They are useful UX ideas but are not needed for the minimal core and would add provider-specific/transcript-oriented behavior. |

The rejected runner pattern is also a containment decision: temporary `.claude/commands` can collide with concurrent work, a nested CLI bypasses the platform's supported delegation path, and cleanup after timeout/failure is not the same as the active writer's process ownership. The provider-neutral core therefore has no provider command path, tool/event name, or second orchestration loop.

## Diagnosing-bugs review

The reviewed upstream is [`mattpocock/skills`](https://github.com/mattpocock/skills) commit `6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`, under `skills/engineering/diagnosing-bugs/SKILL.md`, under its MIT license. The reviewed file blob is `061c25a524acaa93d4534e9e08a793c0a5fe45fd`. Dev Platform vendors none of its files; the pin records review provenance for the independently authored `systematic-bug-diagnosis` capability.

| Upstream behavior | Dev Platform treatment | Reason |
| --- | --- | --- |
| Specific, observable failure loop before causal claims | Adapt | The capability requires a confirmed reproducer or direct evidence and calls an unevidenced cause unconfirmed. |
| Competing falsifiable hypotheses and targeted probes | Adapt | The capability records only concise hypothesis, prediction, probe, and result fields; it never requests chain-of-thought. |
| Regression test before repair, original-reproducer rerun, and debug cleanup | Adapt when a reasonable seam exists | This is the bounded regression and post-fix verification contract; an invalid seam is recorded rather than fabricated. |
| Broad failure-oriented trigger | Narrow | Dev Platform triggers the optional capability for unknown diagnosis only, preserving bounded quick corrections with an established cause. |
| Mandatory display of ranked hypotheses to a user | Reject as a platform requirement | User interaction can be useful, but making it a required checkpoint would create an unrelated execution gate. |
| Captured command/output workflow | Adapt with existing evidence safety | Evidence is bounded and redacted; raw prompts, secrets, sensitive payloads, and hidden reasoning are not retained. |

## Selective domain interrogation

`selective-domain-interrogation` is an opt-in, instruction-only refinement pass for materially ambiguous or explicitly domain-heavy managed work. Enable it only where a repository wants an evidence-first pre-design clarification step:

```bash
python3 scripts/capability_manager.py enable selective-domain-interrogation
python3 scripts/capability_manager.py evaluate selective-domain-interrogation --fixture dev-platform/evals/selective-domain-interrogation-pilot.json --runtime fixture
```

The pass reads bounded repository and provided domain evidence first, resolves repository-answerable ambiguity from that evidence without a user question, and surfaces only the unresolved choices that would materially change the intended outcome. Accepted decisions are folded back into the existing `proposal.md`/delta specs/`design.md`/`tasks.md`; the materialized OpenSpec package stays the single canonical implementation contract. A sufficiently clear task gets no interrogation step, and the capability cannot invent product requirements, create a `CONTEXT.md`/ADR/status ledger, or open a second backlog or plan.

The reviewed upstream is [`mattpocock/skills`](https://github.com/mattpocock/skills) commit `6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`, under `skills/engineering/grill-with-docs/SKILL.md`, under its MIT license. The reviewed file blob is `62b9efb6f991d1b229adee7506962f13ced0c499`. Dev Platform vendors none of its files and fetches none at runtime; the pin records review provenance for the independently authored capability.

| Upstream behavior | Dev Platform treatment | Reason |
| --- | --- | --- |
| Interview loop that stress-tests a plan before acting on ambiguous domain work | Adapt | The capability is a bounded pre-design pass for materially ambiguous or domain-heavy work only. |
| Resolve terminology and hidden decisions before implementation | Adapt | Candidate ambiguities are classified and material ones are resolved before code is written. |
| Ask the human to settle open questions | Narrow | The agent resolves repository-answerable facts from evidence first and asks only for unresolved choices that materially change the outcome. |
| Inline `CONTEXT.md` and ADR ledger updates | Reject | Accepted decisions update the existing OpenSpec artifacts; no parallel context, ADR, or status ledger is created. |
| Tracked design-tree / decision-tree document | Reject as a platform requirement | The materialized OpenSpec package remains the sole canonical implementation contract; no second plan or backlog. |
| Delegate the grilling loop to a subagent that answers on the user's behalf | Reject | Product/intent choices are surfaced to the human, not auto-answered; the capability never invents requirements. |
| Mandatory grilling before every task | Reject | A sufficiently clear request proceeds with no interrogation ceremony. |

## Interoperable agent handoff

`interoperable-agent-handoff` is an opt-in, instruction-only capability for
continuing live work in another context — a fresh session, Codex or another
agent, or a person — when the current context cannot simply be compacted in
place. Enable it only where a repository expects cross-session or cross-provider
continuation:

```bash
python3 scripts/capability_manager.py enable interoperable-agent-handoff
python3 scripts/capability_manager.py evaluate interoperable-agent-handoff --fixture dev-platform/evals/interoperable-agent-handoff-pilot.json --runtime fixture
```

It produces or consumes one compact provider-neutral navigation envelope that
points at canonical state: repository, exact revision, branch/worktree, managed
task/OpenSpec, the provider routing record when one exists, and the canonical
evidence to read. Verified facts, unresolved assumptions, blockers and next
intent are kept separate; an unsupported claim stays an assumption. The receiver
validates repository, revision and managed-task identity first and treats a
mismatch (moved `HEAD`, rebase, superseded task) as stale, re-reading canonical
sources.

The capability composes with the existing provider routing handoff
([model routing](model-routing.md)) rather than duplicating it: the routing
record owns executor selection and delegated write containment, while this
envelope carries only the uncovered cross-session/cross-provider/agent-to-human
navigation context. It starts no work, grants no write access or execution
authority, and performs no GitHub, Development Backlog, Project, OpenSpec or
worktree mutation. Ordinary same-context continuation needs a normal compact and
no envelope. Secrets, raw prompts, chain-of-thought and large diff/spec copies
are never carried — the envelope references canonical sources at their revision
instead.

## Frontend design capabilities

Opt-in frontend design help (`frontend-design` general guidance plus the
`high-end-visual-design` specialized profile) rides this same lifecycle — one
descriptor each, project-owned opt-in, derived provider skills only when
selected. Their design-specific applicability, non-applicability, precedence over
and under a project design system, triggering discipline, and bounded-adaptation
provenance are documented in
[Frontend design capabilities](frontend-design-capabilities.md).

## Web engineering capability pack

Two independent opt-in capabilities cover stack-specific web engineering help and
a separate read-only web/UI critic. They ride the same lifecycle — one descriptor
each, project-owned opt-in, derived provider skills only when selected — and
neither is enabled by default.

| Capability | Role | Applies to | Does not apply to |
| --- | --- | --- | --- |
| `react-next-best-practices` | Stack guidance | Implementation and performance work in a compatible, opted-in React / Next.js (App Router) codebase | Non-React frontends, backend-only work, unsupported major versions; it never changes application dependencies |
| `ui-quality-review` | Advisory critic | A requested UI / web-quality review, accessibility pass, or check that a user-facing change works for keyboard, assistive-technology, form, or small-screen users | Backend work, copy-only edits, and visual-redesign or aesthetic-preference requests |

### `react-next-best-practices` is a slim index

The materialized skill is a compact always-loaded index: applicability,
precedence, and a routing table. The actual rules live in four bounded topic
groups under `dev-platform/capabilities/react-next-best-practices/`
(`server-client-components.md`, `data-fetching-and-waterfalls.md`,
`bundle-and-code-splitting.md`, `rendering-and-re-renders.md`), and the index
tells the agent to read only the group the task needs. The descriptor lists those
group files as dependencies so `audit` fails if one is missing. Stack
applicability is a guidance gate, not a dependency change: enabling the capability
never edits `package.json` or a lockfile.

### `ui-quality-review` is evidence-backed and advisory

Every finding cites a category, a location, the evidence, a severity with who is
affected, an uncertainty note, and the smallest recommended change. An honest
"no findings" with a list of what was checked is a valid result, and the review
lists at least one healthy check so a heuristic cannot over-report. It creates no
code, commit, Issue, Backlog item, or managed task, never proposes a redesign or
a new design language, and its findings do not by themselves block a merge.
Repeated critical requirements become project tests only through a separate
accepted project decision.

### Precedence

For both capabilities, in order of authority: (1) project product requirements
and accepted OpenSpec behaviour; (2) the project-owned design system, brand
guide, component library, or architecture decision; (3) accessibility,
regulatory, and functional-testing requirements; (4) the capability's generic
guidance or checks.

### Triggering discipline

`dev-platform/evals/react-next-best-practices-pilot.json` and
`dev-platform/evals/ui-quality-review-pilot.json` each encode ten positive and
ten hard-negative synthetic prompts, three samples each. The React negatives
include Vue, Svelte, jQuery, plain CSS, and backend controls; the UI-review
negatives include redesign requests, aesthetic-preference requests, and non-UI
controls. They are deterministic CI evidence of the intended trigger boundary,
not a claim about a provider's live routing.

### Provenance — bounded adaptation

Dev Platform vendors no upstream files and fetches none at runtime. Each
instruction file is an independent, bounded adaptation of widely published,
version-pinned guidance; the descriptor records `content_sha256` of the local
file so the effective guidance cannot drift, and adopting newer upstream guidance
is an explicit `python3 scripts/capability_manager.py update <id>` with a
refreshed hash, reviewed like any other change.

| Capability | Reviewed reference | Pinned revision | License | Treatment |
| --- | --- | --- | --- | --- |
| `react-next-best-practices` | [`vercel/next.js`](https://github.com/vercel/next.js) App Router documentation under `docs/` | `8ea76d64ca3931c1beccceb15d32df5d770f4957` (2026-09-02) | MIT | Adapt — Server/Client Component boundaries, request-waterfall and caching/streaming guidance, and dynamic-import code-splitting rewritten provider-neutrally as bounded topic groups. Framework internals, config specifics, and version-specific APIs are not vendored. |
| `react-next-best-practices` | [`reactjs/react.dev`](https://github.com/reactjs/react.dev) learn/reference content | `24618e2ac310ef03b86e60c858a8dbe55869965d` (2026-08-31) | MIT (code) / CC-BY-4.0 (documentation prose) | Adapt — "you might not need an effect", derived state, stable `key`, and measured-memoisation guidance rewritten as the rendering topic group. |
| `ui-quality-review` | W3C [WCAG 2.2](https://www.w3.org/TR/2023/REC-WCAG22-20231005/) | W3C Recommendation 05 October 2023 (immutable dated version) | W3C Document License | Adapt — success-criterion themes (name/role/value, focus visible and order, labels and error identification, reflow, reduced motion) as the review categories, not a conformance checklist. |
| `ui-quality-review` | W3C [ARIA Authoring Practices Guide](https://github.com/w3c/aria-practices) | `7e4034b262bc0d25332e330d8a582aaf34113829` (2026-07-22) | W3C Document License | Reference-only — informs the "native element first, ARIA only where needed" and focus-management expectations. |

## Delivery

The manager, descriptors and guidance are Copier-managed platform surfaces. Fresh renders and reviewed Copier updates are deterministic; an immutable platform release produces ordinary rollout PRs for managed projects. Project-owned harnesses retain their lifecycle implementation.
