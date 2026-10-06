## Context
`openspec_lifecycle.archive` launches review in preflight; `finish_task` requires archive before publication. Workers and coordinator states come from earlier children.

## Decisions
1. Handoff mode for coordinator-managed source candidates: `finish` stops after PR + admission; archive is not required at handoff, but semantic verify receipt and selected-check evidence for the active change are.
2. Review job: runs `independent_review.py run` in a disposable checkout of the exact head via the worker; reports are posted as lifecycle evidence commits by the harness; review identity uses the existing task-content identity.
3. Repair job: given the handoff record and findings, an LLM writer produces commits in a disposable checkout; the harness validates and pushes; content change makes review stale; bound of 3 review/repair rounds before blocked-escalation.
4. Fallback: ordered `providers`; default single provider keeps current behavior.
   Resolve bindings at originating handoff and carry them through repair/retry jobs; never consult a worker's route. Bound consecutive unavailable attempts to three, retaining blocked-retryable evidence after exhaustion. Fence push and advancement with fresh exact-job claim reads. Derive interrupted repair completion from trusted result comments, and protect all lifecycle evidence directories from repair writes.
5. Evidence reuse: required-check results and selected-check evidence are recorded with the task-content identity; archive/finalize accept them for an identical identity.

## Risks and Mitigations
Review comments as evidence on the PR branch could change identity: lifecycle evidence paths are already excluded. Repair loops: bounded rounds and escalation.

## Verification
End-to-end fixture flow developer→PR→review fail→repair→review pass; fallback evidence; reuse vs stale identity; docs/AGENTS contract tests.
