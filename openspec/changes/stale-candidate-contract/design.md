## Decisions

- **Review and repair.** The harness runs no candidate checks there, so the candidate contract is not an input. Their `prepare_checkout` calls pass `dev-platform/source-contract.toml` of the trusted root; a missing file fails naming it. `.dev-platform.toml` is untracked in the source repository, and the coordinator is source-only, so candidate content is untouched.
- **`contract_from`.** The existing parameter installs a contract only when a checkout commits none, which holds here, and `checkout_harness` takes it for the review and repair harness. Composition post-merge keeps its own integration contract.
- **Finalize.** The candidate contract at the exact head is read and validated in job selection, before claim, with the same `validate_platform_config`. A refusal joins the existing `refused` list with the key and the exit. An unreadable contract refuses; there is no other source.
- **Integration kinds.** The contract source is the merged head. The approved ADD assumed the harness read no contract before merging main. That part holds, but implementation found that the harness then read the copy installed at the candidate head, because installation stopped when a copy existed. A stale candidate therefore failed integration repair after the merge. The coordinator chose to correct this: `checkout_harness` and the step before regeneration replace the installed copy with the committed `dev-platform/source-contract.toml` of the head. The writer's checkout stays data only, so it is not refreshed.
- **Replacing the copy.** Installation replaces only an untracked copy. A committed `.dev-platform.toml` of a project moves with the checkout and is never touched. A head with neither contract fails naming `dev-platform/source-contract.toml`.
- **Candidate changing its own contract.** Review reads the trusted contract; the candidate's contract is exercised by its own checks and by finalize.

## Risks

No real stale candidate exists now. A disposable-repository acceptance proves both paths.
