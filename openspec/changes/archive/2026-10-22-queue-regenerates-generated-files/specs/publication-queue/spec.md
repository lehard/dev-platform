## ADDED Requirements

### Requirement: Declared generated files are regenerated on integration

When preparing a candidate on current main, the coordinator SHALL treat files that its default branch declares generated in the committed check configuration as derived. When a merge of current main conflicts only in declared generated files and archive-derived current-spec paths, or a declared generated file changed both in main since the admission base and in the candidate, the coordinator SHALL merge in a disposable checkout, re-derive archive-derived specs as before, regenerate each such file by running its declared command from the default-branch code over the merged tree, and push the result as a recorded coordinator update whose parents are the claimed head and main. Required checks SHALL run on that head and gate the merge unchanged. A failed regeneration, a remaining conflict or a conflict in any other file SHALL become integration repair. The coordinator SHALL NOT execute pull-request-controlled code while holding the App token. Recovery of an unrecorded update SHALL accept a merge that differs from both parents only in archive-derived specs and declared generated files.

#### Scenario: Candidate conflicts with main only in the generated manifest
- **GIVEN** a ready candidate and a main that both changed neighbouring entries of the declared platform manifest
- **WHEN** the coordinator prepares the candidate
- **THEN** it pushes a coordinator merge with a regenerated manifest and records the update
- **AND** required checks run on that head, and after merge `generate_platform_manifest.py --check` passes on main

#### Scenario: Conflict in an ordinary file
- **GIVEN** a ready candidate whose merge with main conflicts in a file that is neither generated nor archive-derived
- **WHEN** the coordinator prepares the candidate
- **THEN** it offers integration repair as before and pushes nothing

#### Scenario: Regeneration fails
- **GIVEN** a candidate whose only conflict is in a declared generated file
- **WHEN** the declared regeneration command fails
- **THEN** the coordinator offers integration repair naming the failure and pushes nothing
