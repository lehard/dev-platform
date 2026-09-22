# Design: One combined trigger for Process and Architecture Health Review

## Boundary

`platform-health-review` is a trigger/orchestration capability, not a review engine. It does not re-implement or change either existing review's reasoning; it only defines when both reviews run together and records that they are presented to a human as one combined function.

## Execution model

Two implementation shapes are both consistent with this design and left to implementation-time choice, provided the observable behavior (one schedule, one manual dispatch, both reviews run) holds:

- extend the existing `weekly-process-backlog-review` gh-aw workflow to also invoke the architecture-health job in the same run, or
- keep both as separate gh-aw workflows sharing one identical schedule/dispatch definition, started together.

Either way, each review keeps its own engine, tools, safe-outputs declaration, and cost/runtime guardrails unchanged; only the trigger is shared/aligned.

## Compatibility and rollback

Existing standalone manual dispatch of either review (if retained as a separate trigger) continues to work. Reverting this change restores two independently triggered reviews with no data/state migration.

## Verification note

`tasks.md` originally listed a live combined-dispatch smoke test in
`lehard/dev-platform` as a pre-archive verification item. As established by
the prerequisite change (`add-architecture-health-cloud-review`), GitHub
Actions only registers a `workflow_dispatch`-triggerable workflow, and
accepts a dispatch request for it, once that workflow's file exists on the
repository's **default branch**. This change's new orchestrator workflow
(`.github/workflows/platform-health-review.yml`) is first-introduced here,
so the same structural constraint applies to it directly, and its two
`workflow_call`-triggered dependencies only become invokable through it once
all three files are on `main`.

Because this repository's lifecycle requires archiving a change before its
PR is published/merged, a genuinely live pre-merge dispatch of a brand-new
combined trigger is not achievable in that order. The live-dispatch
confirmation is therefore an explicit **post-merge** follow-up (see
`tasks.md`), not a pre-archive gate: everything verifiable pre-merge
(recompiling all three workflow sources with the pinned `gh-aw` release,
diffing each review's guardrail/tools/safe-outputs blocks as unchanged,
structural/unit tests including the new combined-trigger shape assertions,
`openspec validate --strict`, and the full platform test suite) was verified
before archive.

## Risks and mitigations

- Risk: combining triggers could accidentally couple failure modes (one review's failure blocking the other). Mitigation: each review keeps its own job/workflow boundary and safe-outputs declaration; a failure in one must not prevent the other's run or its own safe output.
- Risk: doubled AI-credit spend per combined run. Mitigation: guardrails remain per-review as already accepted for each; this change does not raise either review's individual budget.
