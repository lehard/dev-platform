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
requirement digest, a non-empty `target_repository`, an exact
`prepared_against` revision plus its freshness against the current worktree
HEAD, well-formed evidence/reused-constraint/element/assumption entries, and
that `approved: true` is never set while an `unresolved_choices` entry is
`status: "open"` or a `contradictions` entry is `resolved: false`. It never
claims the ADD itself is the right design.

For an unresolved consequential choice -- one where evidence cannot determine
the intended alternative and the alternatives would materially change the
delta -- compose with `selective-domain-interrogation` rather than building a
second interview mechanism; group related material choices into one bounded
checkpoint where practical. An evidence-resolvable fact is recorded as an
already-`resolved` choice and never becomes a question.

### Approval is bound to exact content, not just a flag

`approved: true` alone is not a valid approval. Approving an ADD writes an
`approval` receipt bound to a canonical content digest of the ADD's material
fields (everything except `approved`/`approval` themselves), computed by the
tool -- a human cannot hand-compute a SHA-256 of canonical JSON, so approval
always goes through the CLI:

```bash
python3 scripts/add_intents.py approve-add <add-path> [--approved-by <name>]
```

`approve-add` refuses to approve while any unresolved consequential choice or
contradiction remains, exactly like the `approved: true` gate it now also
enforces on any hand-edit. If the ADD's material content (elements,
evidence, assumptions, reused constraints, requirement digest, ...) changes
*after* approval, `validate-add` detects that the approval's recorded digest
no longer matches the current content and rejects it as a **stale
approval** -- re-run `approve-add` after any material edit.

### Binding evidence to a reusable Project Evidence Snapshot

An evidence entry can be a digest-bound reference into a Project Evidence
Snapshot (see `dev-platform/capabilities/project-evidence-snapshots.md`)
instead of only a free-form `{source, kind, digest}` fact. Build the
reference with that capability's own primitive -- this module never
recomputes snapshot source identity or freshness itself:

```bash
python3 scripts/project_evidence.py reference <snapshot-path> --concern <concern> --require-fresh
```

Fold that command's JSON output into an evidence entry with
`"kind": "project-evidence-snapshot"`, `"source"` set to the snapshot file's
path, and `"digest"` set equal to `projection_digest`:

```json
{
  "source": "<machine-local>/snapshot.json",
  "kind": "project-evidence-snapshot",
  "digest": "<projection_digest>",
  "snapshot_digest": "<snapshot_digest>",
  "snapshot_revision": "<snapshot_revision or null>",
  "projection": "<concern>",
  "projection_digest": "<projection_digest>",
  "projection_status": "<projection_status>"
}
```

Because this evidence kind is machine-checkable, it is treated as
load-bearing: `decompose` re-proves every such entry against the snapshot
file (via `project_evidence.validate_snapshot`) and **refuses to run**, not
merely warns, if the snapshot was rebuilt/changed since the ADD recorded it,
if its digest no longer matches, or if the referenced projection is not
`fresh`. Free-form evidence entries (any other `kind`) are unaffected.

## Intent decomposition

Once an ADD is approved, decompose it into atomic intents:

```bash
python3 scripts/add_intents.py decompose --add <add-path> --out <intents-path>
python3 scripts/add_intents.py validate-intents <intents-path> --add <add-path>
```

`decompose` refuses an ADD that is not `approved`, that fails
`validate-add`, that is stale against the current worktree HEAD, or whose
required snapshot evidence is no longer provably fresh (see above). It
mechanically carries the approved ADD's content digest and any
`project-evidence-snapshot` evidence entries forward onto the scaffolded
intent set as `approved_add_digest` and `snapshot_refs` -- this is bounded
copying of already-proven references, not semantic judgment. Each intent
captures one bounded, independently specifiable outcome: `goal`,
`scope`/`non_goals`, the ADD element ids it `covers`, its `dependencies` on
other intents, `evidence_refs`, and a `ready`/`blocker` state -- never
file-level implementation steps, and never a new architecture decision that
the ADD did not already make. Bounded-empty lists (`scope: []`,
`evidence_refs: []`, ...) are valid wherever a concern does not apply;
`validate-intents` only requires the field to be present and well-typed, not
non-empty. When decomposition cannot bound an intent without inventing or
changing a material decision, that gap returns to ADD refinement instead of
being silently settled inside the intent.

`validate-intents` proves: schema/version validity and a matching `add_id`;
that the intent set's `approved_add_digest` matches the parent ADD's current
approval digest exactly (a mismatched or stale parent binding is rejected,
not merely warned about); that every `new`/`changed` ADD element is `covered`
by an intent or carries an explicit `non_implementation` disposition with a
reason; that dependency, `covers`, and `evidence_refs` references all exist;
that the dependency graph is acyclic; that two intents never claim the same
ADD element without each recording an explicit `overlap_reason`; that no
intent is marked `ready` while it still records a `blocker`; and that any
`snapshot_refs` entry actually matches a snapshot evidence entry the ADD
recorded and is still provably fresh. It never claims the decomposition is
the best possible partition -- that is targeted agent/human review, guided by
the representative evals in `dev-platform/evals/add-intents-pilot.json` and
the semantic atomicity review below.

## Semantic atomicity review (split-candidate criteria)

Deterministic `validate-intents` only proves structural properties: coverage,
acyclic dependencies, and unexplained overlap. Whether a given intent is
*actually* atomic is a judgment call for the agent/human performing
decomposition, guided by these provider-neutral criteria. None of this is
encoded in `add_intents.py`; the Python layer scaffolds and validates
structure only, never architecture.

Treat an intent as a **split candidate** -- return it to decomposition rather
than handing it off as-is -- when it exhibits any of:

- **Independent triggers, policies, or outcomes.** The intent bundles two or
  more pieces of behavior that fire on different triggers, are governed by
  different policies, or produce materially different observable outcomes.
- **Independently verifiable, deliverable, or rollbackable pieces.** Part of
  the intent could be accepted, shipped, or rolled back on its own without
  the rest -- that independence is itself evidence the intent is not atomic.
- **A business outcome mixed with independent infra/platform work.** A
  user/business-facing outcome bundled with unrelated infrastructure or
  platform work that has its own independent lifecycle is a split candidate
  even if both changes happen to originate from the same ADD element.
- **Several component/domain concerns joined only by topic.** If the only
  thing holding the pieces together is that they are "about the same
  feature" rather than a genuine shared outcome, split by component/domain
  instead.
- **A container for several independent changes.** One intent must never
  become a catch-all for multiple changes that each have their own bounded
  outcome; that defeats the purpose of decomposition into atomic units.

Conversely, several intents that genuinely lack independent observable
outcomes and are jointly required for one coherent change may share a single
downstream OpenSpec change (see
`openspec/specs/openspec-authoring/spec.md`, "Several intents are
inseparable") -- but that grouping must be justified against the ordinary
OpenSpec split test, never assumed for convenience. `prepare-handoff` (below)
enforces this mechanically by requiring an explicit `--group-reason` whenever
more than one intent is handed off together.

## Handoff to OpenSpec authoring

An intent that is `ready` (no blocker, bounded scope, ADD/evidence
references) can go directly to normal OpenSpec proposal authoring: the
business goal/context, the intent's outcome/scope/non-goals/dependencies, and
the referenced ADD/evidence become the authoring input, without repeating
broad architecture discovery. The existing OpenSpec split test remains
authoritative for intent-to-change mapping: an intent with an independent
observable outcome is its own change; only genuinely inseparable intents may
share one change.

Produce a bounded, deterministic authoring-input envelope for a selected
ready intent (or an explicitly justified cohesive group) instead of manually
re-collecting the business goal, intent contract, and ADD constraints:

```bash
python3 scripts/add_intents.py prepare-handoff \
  --add <add-path> --intents <intents-path> \
  --intent-id <intent-id> [--intent-id <intent-id> ...] \
  [--group-reason "<why these are inseparable>"] \
  --out <handoff-envelope-path>
```

The envelope carries the business context reference, each selected intent's
outcome/scope/non-goals/dependencies/evidence refs, the approved ADD's
content digest plus the material elements and reused constraints it covers,
and any snapshot/evidence refs -- never generated OpenSpec prose, and never
an autonomously created Issue or PR. Because the ADD, intent set, or a
required snapshot can all change after the envelope was written, re-prove it
before relying on it:

```bash
python3 scripts/add_intents.py validate-handoff <handoff-envelope-path> \
  --add <add-path> --intents <intents-path>
```

`validate-handoff` never trusts the envelope's own recorded digests; it
recomputes each binding from the current ADD/intent-set files and any
`snapshot_refs`, and reports the envelope as stale (rather than silently
usable) the moment any of them has moved.

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

`add_intents.py` only reads/writes the local JSON files it is pointed at,
reads the local Git history for `prepared_against`/freshness comparisons, and
-- for `project-evidence-snapshot` evidence entries -- reads the referenced
snapshot file and calls into `project_evidence.py`'s own validation, never
recomputing snapshot source identity or freshness itself. It never calls a
provider API, opens a network connection, mutates `openspec/changes/`,
Backlog, or Project state, or writes outside the paths its caller names. It
never creates a GitHub Issue or PR; `prepare-handoff` only ever writes the
local envelope file its caller names.
