## Why

The publication coordinator runs unattended in `.github/workflows/publication-queue.yml` on ephemeral runners and as local dogfood. Today its required configuration is validated only implicitly and late: `actions/create-github-app-token` fails on an empty input with a generic error, `DEV_PLATFORM_COORDINATOR_APP` silently resolves to an empty name when the token step output is missing, and `publication_queue.trusted_apps` unions the environment slug with configured names without noticing a contradiction. A misconfigured run can therefore reach candidate work, or run with a trust set different from the one the operator believes.

Meaningful coordinator friction (`publication_queue.emit_friction` -> `integration_contour.default_friction_sink` -> `agent_friction.append_coordinator_event`) is written only to the machine-local `.claude/agent-friction.jsonl`. On a GitHub-hosted runner that file is discarded when the job ends, so the Requirement retrospective (`requirement_retrospective.py`, which reads `agent_friction.events_for_task` from the local log) never sees what the coordinator experienced, while its evidence-source status still reports the local log as `available`.

## What Changes

- Add one repository-owned `publication_queue.py preflight` subcommand with explicit `--mode ci|local` and `--phase inputs|runtime|all`. It validates App identity, trust configuration, permission proof and runtime inputs, prints only input names and fixed categories, and exits non-zero naming the first failing input. The workflow runs it before the App token is minted (inputs, using boolean presence flags so secret values never reach the process) and after (runtime), and `worker` runs the full preflight before observing any candidate. Local dogfood uses the same entrypoint.
- Persist coordinator friction events as a new trusted PR comment record type (`dev-platform-publication-queue:evidence:v1`) on the candidate PR, authored through the existing coordinator token, bound to Requirement, PR number, exact head, lifecycle stage and the resolved worker run identity, idempotent per dedupe key. Continue to mirror the event into the local log for same-machine tooling.
- Extend the Requirement retrospective to read those records: `events_for_task` includes durable events attributed to the Requirement or its linked children, `review-path` lists them with PR/head/stage/worker, `checkpoint` can link or classify them, and an unreadable or malformed durable source is a named evidence-source gap that must be repaired or explicitly accepted.
- Persistence or readback failure is a visible failure: the transition is not published, `worker` exits non-zero with the reason, and the retrospective refuses to treat the source as available.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `publication-queue`: coordinator configuration preflight; durable coordinator evidence record.
- `platform-lifecycle`: the Requirement retrospective consumes durable coordinator evidence and treats an unreadable durable source as a gap.

## Impact

`template/scripts/publication_queue.py` (preflight, evidence record, sink, worker identity), `template/scripts/agent_friction.py` (deterministic coordinator event id, durable merge, source status), `template/scripts/requirement_retrospective.py` (known ids, review-path output), `template/scripts/integration_contour.py` (durable sink), a one-line sink installation in `template/scripts/lifecycle_workers.py`, `.github/workflows/publication-queue.yml`, docs (`docs/engineering/agent-workflow.md`, `docs/managed-rollout.md`) and tests. `scripts/*` shims are unchanged. The `publication-observation` child's fail-closed `trusted_apps` reader and complete comment reader are consumed as-is.

## Success Criteria

A coordinator run with a missing variable/secret flag, empty or contradictory App slug, unreadable trust configuration, wrong token scope or insufficient permission fails in the preflight, before any PR is read, with a message naming the input and containing no credential value. Friction recorded on a discarded runner is visible to `requirement_retrospective.py review-path` from any machine, attributed to the Requirement, head, stage and worker. A failed evidence write fails the run.

## Non-goals

Fail-closed trust reading and comment pagination (owned by `publication-observation`), worker identity redesign (owned by `worker-runtime-identity`), routing coordinator events to GitHub process issues, a new store or journal, changing local friction capture for developer tasks, stable tagging, fleet rollout and the independent pre-release Requirements.
