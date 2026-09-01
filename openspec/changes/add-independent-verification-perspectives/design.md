# Design: Independent review inside the existing completion lifecycle

## Decisions

1. **Two concerns, separate contexts where possible.** Spec fidelity reviews implementation against accepted OpenSpec; engineering quality reviews implementation against architecture, repository rules, maintainability and correctness risks not fully expressed by the spec.
2. **Exact candidate identity.** Review evidence records the candidate head/base or equivalent immutable diff identity.
3. **Existing verification stays authoritative.** Reviewer outputs are evidence/findings consumed by semantic verification and `verification.md`, never a parallel completion status.
4. **Findings require disposition.** Material findings are fixed, explicitly rejected with rationale, or block PASS.
5. **Provider-neutral.** Use delegated/subagent review when available; otherwise expose the missing independence rather than claiming it.
6. **Proportional use.** Do not force heavy independent review onto bounded quick work without a relevant risk trigger.

## Integration contract

Independent review is an opt-in completion-lifecycle capability for material
managed changes. It does not create a second task state, publish anything, or
run a provider from the lifecycle helper. Instead, the platform prepares a
provider-neutral review request that a configured runtime can consume in a
fresh, read-only context, and validates the two returned evidence reports
before an archiveable PASS can stand.

The request records an immutable candidate identity: the base reference and
resolved SHA, candidate HEAD SHA, and SHA-256 of the committed
`base...candidate` binary diff. A report is accepted only when it repeats the
request id and that exact identity. Preparing a new request after the candidate
changes intentionally invalidates older reports.

Each `independent-reviews/<perspective>.json` report has the same bounded
schema:

- `perspective`: exactly `spec-fidelity` or `engineering-quality`;
- the request id and candidate identity;
- reviewer runtime/context metadata asserting `fresh_context: true` and
  `write_access: false`;
- availability, or a truthful limitation when the review could not be
  obtained; and
- findings with severity, evidence, and (for material findings) a disposition.

The spec-fidelity perspective receives the active proposal, design, tasks and
delta specs and asks whether the candidate implements that contract. The
engineering-quality perspective additionally receives repository rules and
architecture guidance and asks about correctness, maintainability, safety and
risks not expressed in the delta. A material finding must be `fixed` or
explicitly `rejected` with a rationale; `blocker`, missing, or unavailable
evidence keeps semantic verification from becoming archive-ready when the
capability is enabled.

The platform owns only request preparation, report validation and lifecycle
gating. An enabled PASS receipt cites the request as
`Independent-Review-Evidence: independent-review-request.json`, keeping the
evidence visible without adding another lifecycle state. The runtime adapter
owns creating the fresh review context and can be replaced without changing the
report schema. This keeps review execution read-only/evidence-only: it has no
platform route to publish code, mutate a Backlog/Project item, archive a
change, or set completion state.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A review report is reused after code or its comparison base changes. | Bind reports to a request id, resolved base/candidate SHAs, and binary-diff hash; recompute the identity during record and readiness checks. |
| A missing runtime is mistaken for independent evidence. | Make the feature opt-in and require an explicit unavailable limitation, which blocks readiness when the gate is enabled. |
| A legacy or minimal checkout receives the lifecycle update before the new helper. | Keep the disabled default compatible with that checkout; if independent review is explicitly enabled without its helper, fail closed with an actionable repair message. |
| Independent review creates a second lifecycle or receives delivery authority. | Keep the platform surface to request preparation, report recording, validation, and archive gating; accept only read-only context attestations and expose no publish, Project, archive, or completion commands. |
| A shared template change silently conflicts with an existing project-owned file. | Register the new script in doctor and adoption collision checks, and retain the existing ownership-safe template update path. |
