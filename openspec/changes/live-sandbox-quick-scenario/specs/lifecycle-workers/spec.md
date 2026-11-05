## ADDED Requirements

### Requirement: Clone and fetch work on a private repository

Queue, worker, composition and absorb-main checkouts of a GitHub repository SHALL authenticate clone and fetch through the same process-scoped credential mechanism as push. The token SHALL NOT appear in argv, URLs, checkout configuration, logs or a writer environment. A missing credential for a private repository SHALL fail with an error naming it.

#### Scenario: Worker checks out a private repository

- **GIVEN** a private repository and a valid token in the worker environment
- **WHEN** the worker prepares a checkout of an exact head
- **THEN** the checkout succeeds
- **AND** the checkout configuration holds no credential

#### Scenario: Token is missing

- **GIVEN** a private repository and no token
- **WHEN** the worker prepares a checkout
- **THEN** it fails with an error naming the missing credential
