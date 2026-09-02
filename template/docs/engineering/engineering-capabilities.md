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

## Frontend design capabilities

Opt-in frontend design help (`frontend-design` general guidance plus the
`high-end-visual-design` specialized profile) rides this same lifecycle — one
descriptor each, project-owned opt-in, derived provider skills only when
selected. Their design-specific applicability, non-applicability, precedence over
and under a project design system, triggering discipline, and bounded-adaptation
provenance are documented in
[Frontend design capabilities](frontend-design-capabilities.md).

## Delivery

The manager, descriptors and guidance are Copier-managed platform surfaces. Fresh renders and reviewed Copier updates are deterministic; an immutable platform release produces ordinary rollout PRs for managed projects. Project-owned harnesses retain their lifecycle implementation.
