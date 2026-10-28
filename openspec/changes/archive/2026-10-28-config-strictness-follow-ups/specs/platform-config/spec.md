## ADDED Requirements

### Requirement: GitHub retry setting is validated

The platform SHALL read `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS` as the bound on GitHub read attempts. When the variable is unset the documented default of 4 attempts SHALL apply. A value that is not an integer or is below 1 SHALL fail naming the variable and the value, and SHALL NOT be replaced by the default or clamped.

#### Scenario: Setting is unset

- **WHEN** `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS` is not set
- **THEN** GitHub reads are attempted at most 4 times

#### Scenario: Setting is invalid

- **GIVEN** `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS` is `abc` or `0`
- **WHEN** a GitHub read runs
- **THEN** it fails naming `DEV_PLATFORM_GITHUB_RETRY_ATTEMPTS` and the value
