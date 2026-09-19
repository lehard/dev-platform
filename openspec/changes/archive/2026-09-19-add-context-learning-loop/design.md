# Design: Extend friction, do not create a second failure system

## Context

The existing lifecycle already has the durable pieces needed for learning: high-signal friction events, sanitization, stable fingerprints, process issues, post-task retrospective, explicit human promotion, and Process Health Review. Project-context learning should be a classification and routing extension over that evidence path.

## Decisions

1. **Reuse `agent_friction.py` as the evidence source.** Do not add `docs/context/failure-log.md`, a transcript store, or another process backlog.
2. **Add bounded context metadata.** Context-gap evidence carries a small classification and likely destination/concern, not a copy of the missing context or raw conversation.
3. **Keep the fingerprint model/provider independent.** The same semantic root cause remains one signal even when executors change.
4. **Repetition is evidence, not automation.** Counts can strengthen confidence, but no threshold directly edits context or creates work.
5. **Promotion remains human-controlled.** Process Health Review may recommend a context improvement; explicit acceptance is still required before managed-task authoring.
6. **Canonical context changes use normal repository review.** A context file is source-controlled project knowledge and should receive the same reviewed change/verification semantics as other durable behavior-affecting guidance.
7. **Preserve existing friction compatibility.** Non-context events and current routing/checkpoint semantics continue to work without mandatory new fields.

## Dependency

This change depends on the bounded project-context ownership/destination model introduced by `lehard/development-backlog#120`. Implementation should consume that current contract rather than duplicating its file layout.

## Verification

Cover context-gap recording, sanitization, deduplication across providers/models, repetition without auto-write, Process Health Review classification, explicit promotion boundary, and unchanged ordinary friction behavior.
