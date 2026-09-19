# Design: Truthful public cutover and fail-closed external delivery

## Context

Development Backlog #118 / PR #436 introduced the intended product boundary, but its verification surface is narrower than its claims in several places. This follow-up is a hardening pass, not a new architecture.

The guiding rule is that a green gate must prove the exact thing it names:

- a public snapshot audit must cover the exact packaged files;
- a history audit must actually inspect bounded reachable history;
- an operator opt-in must be explicit in the project contract;
- a GitLab completion must refer to the exact validated task HEAD and green CI.

## Decisions

1. **One candidate file set for public distribution.**
   Public snapshot code computes a deterministic candidate set once. Audit and packaging both consume that set. Exclusions are explicit product policy, not incidental omissions from scanning.

2. **Sanitize archives/tests/docs too, or exclude them deliberately.**
   Historical OpenSpec archives and test evidence are not exempt merely because they are not runtime code. If they ship in the fresh public product snapshot, they must satisfy the same owner-reference policy. Personal downstream names are replaced by synthetic/example identities where evidence value is preserved. Files that are intentionally not part of the public product are explicitly excluded by distribution policy.

3. **Allow canonical product identity narrowly.**
   The public repository may legitimately need its own canonical source URL/name. That does not authorize arbitrary `lehard/*` references. The sanitization policy documents a narrow allowlist or equivalent classification.

4. **History audit is for secrets, not cosmetic owner-name erasure.**
   Fresh history remains the strategy for old non-sensitive project names. Add a bounded scanner over reachable history/objects for supported credential classes and produce a receipt that states exact scope and limitations. A finding blocks cutover until rotation/revocation/remediation; the scanner does not rewrite history automatically.

5. **Generic guidance has a portable path.**
   Generic renders no longer treat Development Backlog as universal. Portable task/OpenSpec lifecycle is the baseline. Operator-specific managed-task/Project-status/process-health guidance is rendered or surfaced only after explicit operator enablement.

6. **Explicit operator gate precedes environment lookup.**
   `DEV_PLATFORM_OPERATOR_CONFIG` is only consulted when the project configuration says the operator layer is enabled/configured. A global developer shell variable cannot silently opt a random client repository into the owner's control plane.

7. **One operator configuration contract.**
   The external TOML is the canonical operator entrypoint. Rollout registry location lives there. Command-line `--registry` may remain a deliberate override; runtime/docs/tests must share one precedence rule. Avoid requiring a second unrelated registry environment variable for normal operation.

8. **Validate operator state, do not commit it.**
   Add/reuse a doctor-style entrypoint that checks the external config and registry with bounded diagnostics. The user's live inventory remains outside public source and is a post-implementation local operator setup/admin action.

9. **GitLab exact-head evidence.**
   After push, capture current HEAD, resolve the exact MR, verify provider-reported source/target and head SHA, then resolve CI/pipeline evidence for that SHA. Only accepted terminal green status may produce a successful handoff.

10. **No hidden polling contract.**
    The adapter need not wait indefinitely for GitLab CI. Pending/running is a resumable not-ready state. Rerunning status/finish is the supported continuation.

11. **Human merge remains outside bounded adapter.**
    Green CI means ready for human merge/acceptance, not merged/done in production. Do not add auto-merge or deployment here.

12. **Protect GitHub behavior.**
    GitHub publication semantics and exact-head safety remain unchanged except where shared provider-neutral helpers need compatible refactoring.

## Verification strategy

- Public-distribution unit tests prove audit and snapshot share the candidate set and that personal references in archives/tests/docs are caught or intentionally excluded.
- History-audit tests use synthetic Git history containing both a supported fake-secret signature and safe commits; diagnostics must be bounded and secret-safe.
- Render tests inspect the actual no-operator GitHub and GitLab outputs and assert no mandatory Development Backlog/Project-status behavior remains.
- Operator tests prove a global env variable is ignored without explicit opt-in and honored with explicit opt-in; registry lookup follows the documented precedence.
- GitLab tests cover success, head mismatch, failed, pending/running, missing/unreadable pipeline, and no auto-merge.
- Full repository checks and GitHub lifecycle regressions remain authoritative before archive.
