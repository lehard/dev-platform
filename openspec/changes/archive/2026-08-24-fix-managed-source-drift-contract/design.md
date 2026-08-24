# Design: Self-consistent source revision lifecycle

## Decisions

1. **Platform metadata is not user scope.** Deterministic authoring receipt material SHALL not make a newly authored task drift from itself.
2. **Human edits remain meaningful.** Title/body changes outside the normalized platform-owned receipt remain revision changes and stop pre-materialization start unless explicitly acknowledged/superseded.
3. **Content hash remains authoritative.** Comment-driven `updated_at` changes are never sufficient drift evidence.
4. **One recovery entrypoint.** A diagnostic emitted through `dogfood_task.py status` must name a command accepted by that same wrapper, or explicitly name the supported child command.
5. **Materialized OpenSpec stays canonical.** Later Issue drift remains bounded evidence and never rewrites active OpenSpec automatically.
