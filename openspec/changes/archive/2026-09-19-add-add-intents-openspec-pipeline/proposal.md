# Proposal: Add ADD → Intents → OpenSpec authoring pipeline

## Why

Dev Platform currently jumps too quickly from a business requirement to OpenSpec authoring. That forces one agent step to recover current system context, derive new system design, decide unresolved architecture, decompose a large requirement into bounded changes, and author the OpenSpec contract.

The reference intents workflow separates these responsibilities. First it produces a reviewed system-design delta; then it decomposes that approved design into atomic intents; only then are those intents suitable for specification authoring.

Adopt that separation in a clean-room, provider-neutral form:

```text
business requirement
        ↓
current system evidence
        ↓
ADD — Architecture Design Delta
        ↓
human resolution / approval where needed
        ↓
intent decomposition
        ↓
atomic intents
        ↓
OpenSpec authoring
```

ADD and intents are pre-authoring artifacts, not competing lifecycle authorities. OpenSpec remains the implementation contract after materialization.

## What Changes

- Introduce **ADD (Architecture Design Delta)** as the structured delta between a material business requirement and the current accepted system.
- Introduce **Intent** as the atomic, bounded decomposition unit produced from an approved ADD and used as direct input to OpenSpec proposal authoring.
- Reuse existing system decisions instead of re-deciding them in ADD.
- Reuse `selective-domain-interrogation` for unresolved material choices rather than creating a second interview framework.
- Add structural/provenance/freshness gates for ADD and intents, plus semantic evals for representative decomposition quality.
- Prevent the intent stage from silently redesigning decisions already made in ADD.
- Prevent OpenSpec authoring from silently overriding ADD; a material design gap returns to refinement.
- Define greenfield semantics: stack + skeleton establish the initial concrete system baseline; initial accepted OpenSpec is derived from that baseline, and later business requirements use ADD → intents incrementally.
- Keep clear/mechanical changes on the existing lightweight path with no mandatory ADD/intents ceremony.

## Success Evidence

A representative business requirement can be processed so that:

1. accepted system facts and constraints are resolved from bounded evidence;
2. ADD contains only genuinely new/changed system-design consequences;
3. unresolved consequential choices are resolved before ADD approval;
4. approved ADD decomposes into atomic intents with explicit boundaries and dependencies;
5. each material ADD consequence is linked to an intent or an explicit non-implementation disposition;
6. intent decomposition does not re-open architecture already decided in ADD;
7. an intent can be handed to OpenSpec authoring without repeating broad design discovery;
8. OpenSpec becomes canonical for implementation after materialization;
9. a clear bounded change skips the pipeline.

## Reference boundary

At execution time the operator should provide the original `intents-bundle.tar.gz` and the transcript of the author's explanation as **reference-only** context. Use them to understand pipeline semantics, artifact boundaries, decomposition, and gates. Do not vendor/copy the implementation or provider/corporate assumptions; provenance/license is not established.

## Non-goals

- classical ADR/MADR registry;
- permanent intent registry/board;
- Jira/Confluence/GigaCode adapters;
- automatic Issue/PR/task materialization from intents;
- exhaustive whole-repository scanning by default;
- universal automatic greenfield stack selection.
