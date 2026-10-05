## Context
`publication_queue.py` stores admissions and update evidence as `dev-platform-publication-queue:v1` PR comments plus three labels and derives state each run.

## Decisions
1. States are derived from the latest valid v2 marker for the exact head plus labels and checks; labels are a projection (`lifecycle:<state>`), never the source of truth. v1 admissions read as `ready`/`integrating`.
2. Marker schema v2: `{state, head, task_identity, gates: {name: {result, identity, evidence}}, red_gate, not_reverified, attempts, next_job, at}`; written only by trusted coordinator code; malformed markers block with a reason.
3. Status: `publication_queue.py status --pr N` and `--requirement` render state, red gate, attempts and next action; `dogfood_task.py status` includes it.

## Risks and Mitigations
Comment pagination: keep the bounded-page guard and compact markers. Concurrent writers: transitions re-observe head and latest marker before writing.

## Verification
Fixture-based derivation tests, v1 compatibility, restart after lost output, status rendering.
