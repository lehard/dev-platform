## ADDED Requirements

### Requirement: Workers read unchanged GitHub state through the disposable read cache

Lifecycle workers SHALL read PR lists, PR comment histories and Requirement Issue state through the same disposable local read cache as the lifecycle overview, so unchanged reads are revalidated conditionally instead of re-fetched. The cache SHALL never change which jobs a worker offers or claims: job selection, claim expiry and attempt counters SHALL equal those of a cache-free read at the same GitHub state. A corrupt or inconsistent cache SHALL fail the worker run explicitly naming the cache file and its reset, and SHALL NOT be bypassed silently. Claim, result and every other write SHALL bypass the cache.

#### Scenario: Worker poll with nothing changed
- **GIVEN** a warm cache and no change on GitHub
- **WHEN** a worker polls for its next job
- **THEN** it selects the same job as a cache-free poll
- **AND** it spends conditional requests rather than counted re-reads for unchanged PRs

#### Scenario: Corrupt cache stops the worker
- **WHEN** the cache file is corrupt
- **THEN** the worker run fails naming the file and the reset command and claims nothing
