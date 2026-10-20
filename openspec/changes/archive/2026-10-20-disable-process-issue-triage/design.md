## Context

- `process-issue-triage` is the only event-driven gh-aw workflow; it triggers on `issues: labeled` (filtered to `process`) and `workflow_dispatch`. Its gh-aw `conclusion` job reports budget exhaustion and failures as issues/comments.
- GitHub runs `issues` and `workflow_dispatch` events only from workflow files present on the default branch.
- `validate_agentic_workflows.py` compiles a fixed `WORKFLOWS` tuple and diffs their locks; `cloud_maintenance_preflight.py` requires every name in `CLOUD_MAINTENANCE_WORKFLOWS` to exist in `gh workflow list --all` and fails with "metadata is incomplete" otherwise.
- The remaining agentic workflows (`weekly-process-backlog-review`, `architecture-health-review`) are called by the private Platform Health Review.

## Decisions

1. **Delete the source and lock instead of `gh workflow disable`.** Disabling is mutable repository state outside version control and can be re-enabled silently; deletion makes the owner decision reviewable in git and removes every trigger (label, dispatch) and the failure-reporting conclusion job at once. Recompiling the two remaining workflows leaves `.github/aw` metadata consistent.
2. **Drop triage from the validator and preflight lists.** Keeping the name would make validation and the preflight fail on a missing file; it is removed, not tolerated.
3. **Tests assert absence.** A test asserts that neither `process-issue-triage.md` nor its lock exists and that no remaining agentic source triggers on `issues:`, so an accidental reintroduction of event-driven triage fails CI.
4. **Docs name the replacement.** Installed-workflow docs state that event-driven triage is disabled by owner decision (2026-10-19) and that friction/process issues are reviewed by the Process Health Review (`docs/private-platform-health-review.md`); the `gh aw run/logs process-issue-triage` operations example is replaced by the remaining workflows.
5. **Spec.** Remove "Process issue triage reuses a maintained upstream pattern"; replace "Cloud agents are read-only with constrained safe outputs" (whose only scenario was triage) with "Cloud maintenance agents are read-only with constrained safe outputs" covering every installed workflow; add "Event-driven process triage is not installed". "Public pilot reads remain public-only" stays as the constraint for any public-reading workflow; historical archive text is not rewritten.

## Rejected alternatives

- `gh workflow disable` only: invisible in the repository and reversible without review.
- Lowering the budget or narrowing the trigger: still produces failure noise; contradicts the owner decision.
- Scheduled batch triage: rejected by the owner.

## Risks and mitigations

- *Existing triage service issues remain open.* Out of scope by owner decision; the Process Health Review can recommend their disposition.
- *The GitHub workflow record of the deleted file remains listed as historical.* It cannot run without a file on the default branch; the preflight no longer queries it.
