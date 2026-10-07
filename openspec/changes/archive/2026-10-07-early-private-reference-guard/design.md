## Context
The source guard scans current tracked/untracked candidate files, paths, branch, commits and public text with opaque diagnostics. Finish and project_publish already invoke it; archive and shared candidate local checks currently do not.

## Decisions
Reuse scripts/check_private_backlog_refs.py as the sole scanner. Add a reusable template-owned gate that is mandatory when private_lineage is enabled. Missing guard or nonzero result fails explicitly; projects without this opt-in have no private reference policy to enforce. Call the gate in archive before review/checks/OpenSpec mutation, including coordinator finalization. Call it in shared publication before full checks, including draft candidates, preserving later publisher rechecks.

The scan remains over the current candidate rather than a changed-file subset so inherited/archived artifacts and renamed paths remain covered. Do not scan ignored local provenance or historic deleted content. Do not change diagnostic privacy or reference recognition.

## Risks and Mitigation
- Cross-project template rollout: gate only on existing private-lineage opt-in, and test opted-out behavior.
- Expensive review/checks running first: test ordering with sentinels and real scanner fixtures.
- Disclosure: forward only the existing non-disclosing guard diagnostic and test identifier absence.
- Race after early gate: retain publisher guard.

## Verification
Use real temporary Git repositories with explicit configured private Backlog binding; dirty/untracked proposal/design and archived artifacts must fail without archive commands, review, selected checks or shared full checks. Verify clean and missing-guard cases, run relevant test groups and semantic OpenSpec review.
