# Tasks

## 1. Specify the combined trigger

- [x] Add the new `platform-health-review` OpenSpec capability delta describing one combined schedule + manual-dispatch trigger that runs Process Health Review and Architecture Health Review together, with scenarios for a scheduled combined run, a manually dispatched combined run, and an independent-failure scenario (one review's failure does not block the other).

## 2. Implement the shared trigger

- [x] Wire the combined schedule/`workflow_dispatch` trigger across the two existing review jobs (`weekly-process-backlog-review` and the architecture-health cloud job from `add-architecture-health-cloud-review`), without changing either review's own engine, tools, or safe-outputs declaration. Implemented as: each review's own `.md` source drops its independent `schedule:` and keeps `workflow_dispatch:` (standalone use unchanged) plus a new `workflow_call:` trigger; a new plain, non-agentic `.github/workflows/platform-health-review.yml` owns the one shared `schedule` + `workflow_dispatch` and calls both compiled `.lock.yml` workflows as reusable workflows (`uses:` + `secrets: inherit`), with no `needs:` between the two jobs.
- [x] Confirm each review's guardrails (runtime/AI-credit) remain independently enforced per review. Verified by diffing the recompiled lock files: `max-ai-credits`, `max-daily-ai-credits`, `timeout-minutes`, `max-turns`, `tools:`, and `safe-outputs:` blocks are byte-identical to before this change in both `weekly-process-backlog-review.lock.yml` and `architecture-health-review.lock.yml`; only the `on:` trigger block and gh-aw's automatic `workflow_call`-support plumbing (host-repo resolution, artifact-name prefixing, a `pre_activation` membership gate) changed.

## 3. Verify and document

- [x] Manually dispatch the combined trigger in `lehard/dev-platform` and confirm both reviews run for the same trigger event. **Deferred to post-merge** (structural constraint: GitHub only registers a `workflow_dispatch`-triggerable workflow, and accepts a dispatch request for it, once that workflow's file exists on the repository's default branch — see `design.md`'s "Verification note"). After this change merges to `main`, manually dispatch `platform-health-review.yml` and confirm both review jobs run for the same trigger event with no code/PR/managed-task mutation; file any follow-up as ordinary process evidence, not a blocker for this change.
- [x] Run `openspec validate --strict` for the change, full platform test groups, and semantic OpenSpec verification; record truthful evidence in `verification.md`.

## Logical commits

- [x] Commit the OpenSpec delta and the trigger wiring together, since they jointly define one observable capability: both reviews running together on one combined trigger.
