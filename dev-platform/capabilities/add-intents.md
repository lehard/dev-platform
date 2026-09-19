# ADD -> Intents pre-authoring pipeline

Use this capability to translate a material business requirement into OpenSpec
authoring through two bounded pre-authoring stages instead of one agent step
that must simultaneously recover system context, invent architecture,
decompose scope, and author OpenSpec:

```text
business requirement
        -> ADD (Architecture Design Delta)
        -> human resolution/approval where a consequential choice is unresolved
        -> Intent decomposition
        -> OpenSpec proposal authoring
```

ADD and Intents are **bounded pre-authoring evidence**, not a second backlog,
implementation contract, or current-system registry. Once an intent has
produced a managed OpenSpec change, that OpenSpec package is canonical for
implementation, verification, and archive; no ADD/intent file is
synchronized afterward.

## When it applies

Enable this only for work whose business requirement implies a genuine
system-design delta: new or changed capabilities, component/integration
boundaries, contracts, data ownership, invariants, security/trust concerns,
or material non-functional behavior. A clear, bounded change with no useful
design delta skips this pipeline entirely and goes straight to the normal
task-intake lifecycle in [docs/engineering/task-intake.md](../../docs/engineering/task-intake.md).

## ADD (Architecture Design Delta)

An ADD records only the *new or changed* consequences of a requirement
relative to the current accepted system -- not a restatement of decisions the
system has already made. Where accepted OpenSpec, an active delta, project
context, or code/tests already determine a choice, the ADD references that
existing constraint instead of presenting it as a new decision.

Scaffold and validate an ADD with:

```bash
python3 scripts/add_intents.py new-add \
  --add-id add-<slug> --requirement-file <path> \
  --target-repository <owner/repo> --out <path>
python3 scripts/add_intents.py validate-add <path>
```

`validate-add` proves only *structural* properties: schema validity, a bound
requirement digest, an exact `prepared_against` revision plus its freshness
against the current worktree HEAD, well-formed evidence/element entries, and
that `approved: true` is never set while an `unresolved_choices` entry is
`status: "open"` or a `contradictions` entry is `resolved: false`. It never
claims the ADD itself is the right design.

For an unresolved consequential choice -- one where evidence cannot determine
the intended alternative and the alternatives would materially change the
delta -- compose with `selective-domain-interrogation` rather than building a
second interview mechanism; group related material choices into one bounded
checkpoint where practical. An evidence-resolvable fact is recorded as an
already-`resolved` choice and never becomes a question.

## Intent decomposition

Once an ADD is approved, decompose it into atomic intents:

```bash
python3 scripts/add_intents.py decompose --add <add-path> --out <intents-path>
python3 scripts/add_intents.py validate-intents <intents-path> --add <add-path>
```

`decompose` refuses an ADD that is not `approved` or that fails
`validate-add`. Each intent captures one bounded, independently specifiable
outcome: goal, scope/non-goals, the ADD element ids it `covers`, its
`dependencies` on other intents, and evidence references -- never file-level
implementation steps, and never a new architecture decision that the ADD did
not already make. When decomposition cannot bound an intent without inventing
or changing a material decision, that gap returns to ADD refinement instead
of being silently settled inside the intent.

`validate-intents` proves: schema/version validity and a matching `add_id`;
that every `new`/`changed` ADD element is `covered` by an intent or carries an
explicit `non_implementation` disposition with a reason; that dependency
references exist and the dependency graph is acyclic; that two intents never
claim the same ADD element without each recording an explicit
`overlap_reason`; and that no intent is marked `ready` while it still records
a `blocker`. It never claims the decomposition is the best possible
partition -- that is targeted agent/human review, guided by the representative
evals in `dev-platform/evals/add-intents-pilot.json`.

## Handoff to OpenSpec authoring

An intent that is `ready` (no blocker, bounded scope, ADD/evidence
references) can go directly to normal OpenSpec proposal authoring: the
business goal/context, the intent's outcome/scope/non-goals/dependencies, and
the referenced ADD/evidence become the authoring input, without repeating
broad architecture discovery. The existing OpenSpec split test remains
authoritative for intent-to-change mapping: an intent with an independent
observable outcome is its own change; only genuinely inseparable intents may
share one change.

If OpenSpec authoring discovers that the approved ADD is insufficient or must
materially change, that gap returns to ADD/intent refinement rather than
letting `proposal.md`/`design.md` silently become the first place a new
consequential decision is made.

## Greenfield

For a new project, select the stack and create the skeleton first, then
derive the initial accepted OpenSpec baseline from the intended requirements
plus the actual skeleton. Do not create an upfront classical ADR catalog
merely to initialize the project; later material requirements use
`ADD -> intents -> OpenSpec` incrementally against that baseline.

## Storage and lifecycle boundary

ADD and intent-set documents are plain JSON files the operator keeps wherever
task-local, non-authoritative state already lives (for example inside the
task worktree, outside `openspec/changes/`); this capability does not
introduce a directory convention, registry, board, or status ledger for them.
After an intent's OpenSpec change is materialized, ordinary managed OpenSpec
lifecycle rules govern implementation, verification, archive, and
publication -- no ADD-specific implementation status is required.

## Reference boundary

The capability's design was informed by reviewing a third-party "Intents"
skill bundle and its author's own walkthrough, provided out-of-band at
authoring time, strictly as **reference-only** material for understanding
staging and semantics -- particularly ADD/ADR approval, decomposition into
bounded units, and structural gates ahead of specification authoring. Dev
Platform vendors none of that bundle's files, scripts, or corporate/provider
assumptions (Jira, Confluence, GigaCode, Sber, Kafka, functional-area,
provider-session concepts); the schemas, gates, and CLI above are an
independently authored, clean-room, provider-neutral implementation.

## Safety boundary

`add_intents.py` only reads/writes the local JSON files it is pointed at and
reads the local Git history for `prepared_against`/freshness comparisons. It
never calls a provider API, opens a network connection, mutates
`openspec/changes/`, Backlog, or Project state, or writes outside the paths
its caller names.
