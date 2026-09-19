# Proposal: Add reusable Project Evidence Snapshots

## Why

Agents repeatedly reconstruct current project state from repository sources even when the relevant evidence has not changed. This wastes context/tokens and makes staged workflows such as ADD → Intents repeat discovery.

Introduce a provider-neutral Project Evidence Snapshot substrate: deterministic source identity/freshness first, compact semantic projections second, and reuse before model calls. Project-owned context remains canonical reviewed knowledge; snapshots are derived, machine-local evidence.

## What Changes

- Add exact-revision/source-identity manifests and independently invalidatable semantic projections.
- Prefer deterministic preprocessing and existing routine/read-only context workers for extraction.
- Escalate conflicts or low-confidence interpretation instead of silently resolving them.
- Expose stable snapshot/projection digests to downstream consumers such as ADD/Intents and repository goal scans.
- Record bounded reuse/rebuild/worker/escalation efficiency evidence without transcripts.

## Success Evidence

Unchanged sources reuse a projection with zero model calls; a bounded source change rebuilds only affected projections when dependencies prove that safe; stale/conflicting evidence is surfaced; downstream consumers can bind to a snapshot digest; no canonical project source is mutated.

## Non-goals

No vector DB, RAG service, permanent knowledge graph, second source of truth, universal whole-repo scan, production R1 task routing, ADD construction, intent decomposition, or orchestration lifecycle.
