# Platform rollout delta

## ADDED Requirements

### Requirement: Machine-owned Copier metadata is normalized before strict diff validation

Managed rollout SHALL normalize only `.copier-answers.yml` machine-owned trailing newline formatting after Copier update and before strict Git whitespace validation. Other downstream files SHALL remain subject to unmodified strict validation.

#### Scenario: Copier emits an extra blank line at EOF

- **WHEN** an exact-version Copier update leaves multiple trailing newlines in `.copier-answers.yml`
- **THEN** rollout rewrites that metadata file to exactly one terminating newline before running `git diff --check`

#### Scenario: Another project file contains a whitespace error

- **WHEN** the downstream update contains a whitespace error outside the explicit Copier metadata normalization
- **THEN** strict `git diff --check` still blocks rollout before push or PR creation
