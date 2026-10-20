## ADDED Requirements

### Requirement: Sandboxed writer containment is proven by reproducible negative probes

The platform SHALL provide a reproducible probe command that launches a real sandboxed Claude writer against a synthetic integration repository, linked worktree and bare remote, has it attempt to write into the integration checkout, move its refs through the shared Git directory, push to the remote, call the GitHub API and read SSH, GitHub CLI and keychain credentials, and then verifies from the harness that the integration content, refs and remote are unchanged. The command SHALL never print the writer credential and SHALL exit non-zero when any probe succeeded or any harness-side check changed.

#### Scenario: All probes refused
- **WHEN** the probe command runs on macOS with the sandboxed writer launch
- **THEN** every probe is reported refused, the integration and remote are unchanged and the command exits zero

#### Scenario: A probe succeeds
- **WHEN** any probe action succeeds or the integration or remote changed
- **THEN** the command exits non-zero naming that probe
