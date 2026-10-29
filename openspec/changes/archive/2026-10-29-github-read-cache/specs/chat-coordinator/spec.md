## MODIFIED Requirements

### Requirement: Lifecycle overview is a read-only projection of GitHub state

The platform SHALL provide a read-only lifecycle overview that, from GitHub alone (PR heads, checks, labels, versioned marker comments, claim and result receipts, Requirement Issues and Project statuses), shows a summary of all open lifecycle work and a drill-down for one PR or one Requirement. It SHALL write no GitHub comment, label or status and SHALL treat GitHub as its only source of truth. It MAY keep one local, disposable read cache of GitHub GET responses, revalidated by ETag on every read, and SHALL produce the same overview with that cache present, stale or deleted. A corrupt or inconsistent cache SHALL fail explicitly naming the cache file and how to reset it, and SHALL NOT be replaced by a silent full re-read. It SHALL cite for every reported fact the GitHub object or record field it came from. It SHALL consider exactly the candidate set that lifecycle workers consider and SHALL state any bound of that set. A new, unrelated chat session SHALL obtain an equivalent overview with no earlier conversation.

#### Scenario: Cold session asks for the state of all work
- **WHEN** the overview is run from a fresh checkout with only repository access
- **THEN** it lists every open lifecycle candidate and active Requirement with stage, current attempt/round, source links and next operation
- **AND** it performs no GitHub write

#### Scenario: Candidate set matches the workers
- **WHEN** a merged candidate has an open post-merge obligation inside the workers' discovery bound
- **THEN** the overview lists it
- **AND** a merge outside that bound is reported as outside the stated bound rather than omitted silently

#### Scenario: Required source is unreadable
- **WHEN** a PR's comments, checks or a Requirement's progress cannot be read or contradict each other
- **THEN** that item is reported `unknown` naming the failing source
- **AND** it is never reported as healthy or delivering

#### Scenario: Repeated overview without GitHub changes
- **GIVEN** a warm read cache and no change on GitHub since the previous overview
- **WHEN** the overview is run again
- **THEN** its result equals a cache-free read
- **AND** it spends only conditional requests that return 304 plus a bounded number of counted requests

#### Scenario: Change after the previous read is reflected
- **GIVEN** a warm read cache
- **WHEN** a PR comment is added or edited, or the PR state changes, after the previous read
- **THEN** the next overview reflects the change and a 304 never hides it

#### Scenario: Corrupt cache
- **GIVEN** a cache file that is unparsable, has an unknown version or an entry whose digest does not match
- **WHEN** the overview is run
- **THEN** it fails with an error naming the cache file and the reset command
- **AND** it does not silently re-read everything instead

#### Scenario: Deleted or stale cache
- **WHEN** the cache file is absent or an entry is merely out of date
- **THEN** the overview reads from GitHub without error and returns the same result
