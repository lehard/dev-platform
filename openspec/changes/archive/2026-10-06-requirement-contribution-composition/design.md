## Context
`execute_requirement.advance` starts one child at a time; `requirement_integration` builds an append-only shared draft PR of archived children.

## Decisions
1. Source checkouts with coordinator publication enabled use the contribution path; downstream checkouts retain the existing archived-child multi-child delivery path. Integration branch `requirement/BR-N` from main at first child start; contribution PRs base on it; dependent children start from it after predecessors merge into it.
2. Contribution merge by the coordinator with the same harness rules; conflicts between contributions use integration-repair at contribution level.
3. Composition review: a review mode whose diff is the Requirement PR with already-reviewed child identities summarized and only cross-child interactions and the Requirement outcome in scope.
4. Finalization archives all children's changes once on the Requirement candidate. A single source child publishes its active candidate for coordinator review before finalize archives it.
5. Child review identity is validated at the preserved child head with contribution-base and integration ancestry. Later reviewed contributions and composition repairs may extend shared files; composition identity and review bind the resulting tree. Child receipts remain preserved.
6. Contributions pass through finalize to rerun selected checks after repair, then receive a contribution-integration job without archive. Changed content invalidates semantic verification: finalization stops in blocked-retryable with a semantic-verification gate until the developer supplies fresh semantic verification and a refreshed content-bound receipt through the handoff path. The harness never rebinds an old PASS receipt.
7. Finalized compositions receive a claimed pre-merge retrospective job on the existing retrospective worker path. Its parent checkpoint and content-bound gate precede exact-head full checks and admission.

## Risks and Mitigations
Parallel children editing shared files: contribution merge conflicts are repaired before composition; composition review targets cross-child contracts.

## Verification
Three-child fixture with parallel and dependent children, composition review scope test, single-finalization test, single-child degenerate path.

Composition review resolves canonical task-content paths to their actual active or archived Git paths, retaining deletion paths. An interrupted archive push re-offers finalization on the recovered head to restore its finalization gate. Failed required contribution checks publish a repair-pending transition and runnable repair job. Full validation uses a credential-free environment and a disposable isolated home.

## Independent-review repairs
Requirement resume reads trusted contribution lifecycle ownership before starting any child; coordinator-owned children remain in flight even across a head update. A refreshed handoff can reset admission only after a same-candidate blocked-retryable semantic-verification stop, with all developer gates bound to the refreshed identity. Other head changes retain the exact-head refusal. Queue inventory filters by the queue label before applying its bound, preserving interrupted merged-contribution recovery while excluding unrelated historical PRs. Composition review binds explicit configured providers or the mandatory children's durable originating routes at offer time, and retries preserve that binding.

After the exact Requirement merge, the existing bounded retrospective and cleanup jobs fan out over the exact manifest's child source branches, PR numbers and heads before completing the parent obligation. Operations are idempotent; interruption retries the bounded manifest set and refusal blocks the job. Harness pushes use an ephemeral Git extraheader scoped to the disposable clone's GitHub origin and sourced from the coordinator token; credentials never enter writer checkout config, command arguments or error output.

All harness pushes share `push_validated` authentication when no explicit push environment is supplied. Single-child resume observes trusted lifecycle ownership and remote head advancement before developer publication and reports an in-flight child. Composition branch friction resolves directly to the Requirement; the pre-merge parent checkpoint selects these attributed events. Required friction writes precede transition publication: storage or lineage failures raise and leave the prior lifecycle state available for retry, rather than permitting an unrecorded transition.
