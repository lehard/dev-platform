# Design

## Decision placement

Use `docs/decisions/README.md` as a short index and record contract, with one immutable-history Markdown record per consequential decision. A record has stable ID, status, scope, date, revision, rationale, alternatives and evidence links, revisit triggers, and supersession links. Later decisions receive new IDs and link backward; the old record gains only a superseded pointer, preserving its historical rationale.

## Authority and discovery

AGENTS.md and the agent-instruction guidance point to the index when a concern has an applicable decision. Records supply context for authoring; OpenSpec remains normative for executable behavior and active deltas. Requirements/Backlog manage work, while ADD remains temporary pre-authoring evidence. Tool-specific instruction files continue to point to AGENTS.md.

## TeamAI migration

Keep `docs/engineering/upstream-evaluations/teamai.md` as the detailed pilot evidence and per-capability substitution record. The new decision summarizes its conclusion and links the evidence rather than duplicating the transcript. Update upstream substitution guidance to identify the registry entry as the durable cross-runtime decision summary while preserving the evaluation document as the pilot record.
