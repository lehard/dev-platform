# Platform rollout stabilization requirements

## Requirement: Copier upgrades are tested, not assumed

Before a platform release is published, CI SHALL exercise a real Copier update from the latest stable platform template (or an explicit bootstrap baseline when no version tag exists) to the candidate template.

The smoke project SHALL contain project-owned modifications before update and SHALL fail validation if those modifications are lost or unresolved conflicts remain.

## Requirement: unresolved template-update conflicts block completion

Generated project doctor SHALL report a blocking failure when a non-ignored `*.rej` file exists or Git reports leftover conflict markers in staged/working-tree changes.

## Requirement: platform tool versions are deliberate

The Project Factory SHALL declare a minimum Copier version and the platform SHALL record the version it was tested with. Platform CI SHALL use the exact tested Copier version rather than a floating compatible range.

## Requirement: central GitHub Actions are immutable references

Third-party/GitHub-owned Actions used by central platform workflows SHALL use full commit SHAs. Mutable major tags SHALL NOT be used in central workflows.

## Requirement: Copier releases use stable version tags

Published Project Factory versions SHALL use stable SemVer Git tags. A published version tag SHALL NOT be moved or reused.

Reusable downstream CI MAY be associated with the same platform release but SHALL continue to execute from an explicit full commit SHA.

## Requirement: release publication fails closed

Automated version publication SHALL refuse to move an existing version tag to a different commit. Downstream project upgrades SHALL remain reviewed and SHALL NOT auto-merge as part of this change.
