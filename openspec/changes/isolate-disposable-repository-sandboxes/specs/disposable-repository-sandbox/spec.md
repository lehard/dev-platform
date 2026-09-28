## ADDED Requirements

### Requirement: Disposable repository copies have independent mutable state

Dev Platform SHALL provide a supported disposable repository creation path that uses standard Git and filesystem operations to make a standalone copy under an explicit sandbox root. The copy SHALL NOT share mutable Git object inodes, object alternates, Git common-directory metadata, or hardlinked workspace files with its source or another worktree. A failed isolation check SHALL prevent the copy from being reported usable.

#### Scenario: Local source repository is copied

- **WHEN** an agent creates a disposable repository from a local source using the supported path
- **THEN** its Git objects and metadata are independent of the source
- **AND** ordinary modifications and permission changes inside the copy do not change source object modes or content

### Requirement: Recursive sandbox operations require proven containment

Before recursively changing permissions or deleting a disposable repository through the supported path, Dev Platform SHALL verify ownership of the exact copy, containment within the declared sandbox root, and absence of shared mutable Git or workspace state. A failed or indeterminate check SHALL stop before mutation and report the unsafe path or condition. The operation SHALL NOT traverse symlinks outside the exact disposable copy or act on integration and sibling worktrees.

#### Scenario: Copy has hardlinked loose Git objects

- **GIVEN** a disposable copy has a Git object hardlinked to an object in an integration checkout
- **WHEN** cleanup is requested
- **THEN** cleanup refuses before changing permissions or deleting the copy
- **AND** the integration object retains its content and mode

#### Scenario: Copy uses linked Git metadata or object alternates

- **GIVEN** the copy has `.git` indirection, a Git common-directory link, or an object alternate
- **WHEN** verification or cleanup runs
- **THEN** it refuses with an actionable diagnostic before mutation

#### Scenario: Copy path escapes its declared root

- **GIVEN** a symlink or path substitution makes the copy or a traversed path resolve outside the declared sandbox root
- **WHEN** verification or cleanup runs
- **THEN** the operation refuses without modifying the external path

### Requirement: Agent guidance uses the supported sandbox contract

Agent-facing instructions for disposable repository copies SHALL identify the supported creation and pre-cleanup verification path and the conditions that stop destructive operations. Regression evidence SHALL cover local-clone hardlink behavior and preservation of shared Git state.

#### Scenario: Agent prepares a disposable pilot repository

- **WHEN** the agent follows the platform sandbox guidance
- **THEN** it uses the supported isolated copy path or proves equivalent isolation before recursive cleanup
- **AND** an unsafe copy is not cleaned by a best-effort fallback
