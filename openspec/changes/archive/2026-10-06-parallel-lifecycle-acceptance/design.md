## Context
The disposable repository sandbox provides independent mutable copies with containment.

## Decisions
1. Scenario uses fake provider commands and a fixture GitHub adapter so it is deterministic and offline; it exercises the real coordinator and worker code.
2. The real dogfood run is deferred to lehard/development-backlog#391 (after BR-353 merges); this change ships only the evidence template in its evidence directory, and no run is claimed.

## Risks and Mitigations
Fixture drift from real GitHub semantics: the deferred dogfood run (#391) is meant to complement the sandbox.

## Verification
Repeated scenario runs; the dogfood evidence template review (the real run is verified under #391).

## Sandbox scenario implementation notes
- `template/scripts/parallel_lifecycle_acceptance.py` (source adapter `scripts/parallel_lifecycle_acceptance.py`, command `run --output <dir>`) runs three candidates admitted before any merge: A (managed, clean), B (managed; a material review finding, a real repair, a fresh review, finalization, main movement through `update-branch`) and C (managed; finalized, then its edit conflicts with A, so the coordinator offers integration repair, and the content-changed candidate is re-reviewed against its archive and finalized again). Merges are sequential A, B, C and every post-merge obligation (retrospective, terminal reconciliation, cleanup) terminates.
- Real: coordinator transitions and records, claims, job derivation, task-content identity, review/repair/finalize/integration-repair executors, harness-owned clones and validated pushes, sandbox creation and containment verification, post-merge jobs. Local stand-ins: a strict in-process `gh` adapter over a real bare Git remote (heads observed from refs, protected squash merge, stale expected heads and checks for another head refused, unsupported calls fail and fail the run), a deterministic reviewer launcher that reads the actual fixture content, scripted writer commands, a scripted archiver that reproduces the archive move and spec materialization (the trusted OpenSpec archive entrypoint is not exercised offline), and a fake Requirement/Project operator surface for post-merge reconciliation.
- A candidate whose task content changed after review needs a content-bound developer semantic-verification handoff before finalization (existing finalization contract). The scenario scripts exactly that and records it as a `developer_actions` entry, separate from `operator_actions`, which must stay empty.
- Platform gap found and fixed by this change: an integration repair that changes task content of an already finalized (archived) managed candidate returned it to review, but the review job looked only for the active change directory and left the candidate in `reviewing`. `pr_review_gate.execute_review` now resolves the change through its archive, with a focused regression test, and the scenario exercises the path.
- Operator actions are observed at the local GitHub adapter (a mutation while the adapter's actor is `operator`); the scenario never sets that actor, so a manual completion step would make the structured check fail.
- Runtime is about 30 seconds per run on a laptop, dominated by Git subprocesses; the two runs of the test execute concurrently in separate roots.

## Portability notes for downstream rollout
Downstream rollout is a separate Requirement; these are the inputs it must map, not work done here. The real dogfood run is deferred to lehard/development-backlog#391 and has not happened.
- **Provider mapping:** reviewer perspectives need two independent contexts from a configured provider (`[independent_review] provider`/`providers`); the reviewer binary must be resolvable on the worker host. Repair and integration-repair writers are an operator-configured `--llm-command` with bounded `--allow` paths; the sandbox uses scripted commands and never needs a provider.
- **Check mapping:** protected `main` must register at least one required check, because `not_registered` blocks a candidate; the sandbox adapter's single fixture check stands in for the project's required checks, and finalization re-runs the project's selected-check command in the worker checkout.
- **Trust configuration:** lifecycle markers, claims and results are trusted only from repository OWNERs, proven writers or the configured coordinator App (`[publication] coordinator_app`); workers need the same trust model as the coordinator, and a worker credential must never reach writer or reviewer processes.
- **Worker hosting:** separate worker processes per job kind with unique worker names, a claim TTL longer than the longest job, a scratch HOME per job, and an HTTPS push credential available only to the harness push; post-merge workers need the Requirement and Project operator credentials that the sandbox replaces with a fake surface.
- **Pinned tools:** the OpenSpec CLI at the platform-pinned version must be pre-installed on finalize/re-derivation workers (never installed at run time), plus Git with `merge-tree --write-tree`.
- **Protected-branch setup:** squash merges with exact `--match-head-commit`, strict up-to-date branches, required checks, branch updates by the coordinator App only, and no bypass for the worker identity; `refs/pull/N/head` must be fetchable from the coordinator checkout.
- **Not portable from the sandbox:** the sandbox proves lifecycle logic and containment, not GitHub permissions, rate limits, check scheduling latency or provider availability; those belong to the dogfood run.
