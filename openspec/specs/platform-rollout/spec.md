# Platform rollout

## Requirements

### Requirement: Copier upgrades are tested, not assumed
Before a platform release is published, CI SHALL exercise a real Copier update from the latest stable platform template (or an explicit bootstrap baseline when no version tag exists) to the candidate template. The smoke project SHALL contain project-owned modifications before update and SHALL fail validation if those modifications are lost or unresolved conflicts remain.

### Requirement: Unresolved template-update conflicts block completion
Generated project doctor SHALL report a blocking failure when a non-ignored `*.rej` file exists or Git reports leftover conflict markers in staged/working-tree changes.

### Requirement: Platform tool versions are deliberate
The Project Factory SHALL declare a minimum Copier version and the platform SHALL record the version it was tested with. Platform CI SHALL use the exact tested Copier version rather than a floating compatible range.

### Requirement: GitHub Actions references are immutable
GitHub-owned Actions used by platform-managed workflows SHALL use full commit SHAs rather than mutable major tags.

### Requirement: Platform releases use stable immutable versions
Published Project Factory versions SHALL use stable SemVer Git tags. A published version tag SHALL NOT be moved or reused, and automated publication SHALL fail closed when an existing tag points elsewhere.

### Requirement: Downstream upgrades remain reviewed
Platform-managed files, including self-contained CI, SHALL propagate to downstream repositories through reviewed Copier updates rather than mutable remote execution. Downstream update PRs SHALL NOT auto-merge by default.
