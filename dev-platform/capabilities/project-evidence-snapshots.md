# Project Evidence Snapshots

Use this opt-in capability when a staged workflow would otherwise repeatedly
rediscover the same bounded repository facts — for example before ADD/Intents
authoring or a targeted repository-goal scan. A snapshot is a machine-local,
derived cache of source identities and compact semantic projections. It is not
an architecture registry, a RAG service, a second backlog, or an implementation
contract.

OpenSpec, `docs/context/`, `AGENTS.md`, code, tests, and their existing owners
remain canonical. A snapshot only names the exact evidence it derived from and
never updates those sources.

## Build before semantic work

First run deterministic inventory/freshness preflight. Keep the output in an
existing machine-local task/evidence location, not in `openspec/changes/` or a
reviewed project-context directory:

```bash
python3 scripts/project_evidence.py build --out <machine-local>/snapshot.json
```

The initial output may mark a projection `requires-extraction` and includes a
bounded `worker_request`. If a previous snapshot is available, pass it with
`--prior`; every projection whose declared source identities still match is a
hit and needs no model call:

```bash
python3 scripts/project_evidence.py build \
  --prior <machine-local>/snapshot.json \
  --out <machine-local>/next-snapshot.json
```

The inventory is limited to the initial concerns (accepted system, topology,
integrations, rules, project context, conflicts/unknowns). It deliberately does
not whole-repository scan or use modification times as truth. Git blob identity
is preferred for the actual local content; SHA-256 is the fallback.

## Use the existing read-only worker path

Do not create a scheduler, nested provider CLI, or another routing record for
snapshot extraction. Hand each emitted `worker_request` to the already selected
routine/read-only context-worker path. The worker has no write authority and
returns only the versioned result shape: facts with evidence references,
conflicts, unknowns, confidence, and an optional existing routing/provenance
reference. It must not return a transcript, private reasoning, bulk source
copy, estimated token usage, or a new architecture decision.

Supply that bounded result on the next build:

```bash
python3 scripts/project_evidence.py build \
  --prior <machine-local>/snapshot.json \
  --worker-result project-context=<machine-local>/project-context-result.json \
  --out <machine-local>/next-snapshot.json
```

Facts are valid only when their `evidence_refs` name one of that projection's
declared source paths. `confidence: low` or a non-empty `conflicts` list is
never promoted to a fresh fact set: the projection is marked
`escalation-required` for stronger review. The routine worker does not settle
the disagreement.

## Bind consumers to digests, not a context dump

Consumers request one concern and bind to the snapshot/projection digests:

```bash
python3 scripts/project_evidence.py reference <machine-local>/snapshot.json \
  --concern project-context --require-fresh
```

The command exposes source freshness separately from the projection status. A
new Git revision with unchanged declared dependencies is `stale-revision` for
the old snapshot but still allows the next build to reuse independently proven
projections. Changed/added/removed bounded sources are `stale-sources` and
require only their affected dependency closure to rebuild. A consumer that
cannot prove both current evidence and a fresh projection refreshes or
escalates before relying on it.

## Validate and keep evidence truthful

```bash
python3 scripts/project_evidence.py validate <machine-local>/snapshot.json --require-fresh
```

Validation proves schema, safe paths, source linkage, exact identities,
projection and snapshot digests, and current freshness. It does not prove that
the semantic extraction is complete or correct. Snapshot efficiency records
only hit/rebuild counts, supplied worker-call count, escalation count, elapsed
time, and a bounded existing provenance reference where available. Token usage
and unavailable runtime fields remain unknown rather than guessed.
