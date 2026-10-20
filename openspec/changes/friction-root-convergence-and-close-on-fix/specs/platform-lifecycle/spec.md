## ADDED Requirements

### Requirement: One root cause keeps one open friction record

A friction issue SHALL be able to carry several fingerprint markers, and routing SHALL add an event as an occurrence of the open issue that carries the event's fingerprint marker. An event left in the `candidate` route state SHALL be resolvable by an explicit decision that either attaches it to a named open friction issue, which then also carries the event's fingerprint marker, or creates a new root issue. Already open duplicates of one root SHALL be consolidable into one issue by an explicit command that moves their markers and closes them with a reference to the kept issue. A target that is not an open router-generated friction issue SHALL be a named error.

#### Scenario: A known root recurs under a new category

- **GIVEN** an open friction issue N for a root, and an event with another category left in `candidate` state pointing at N
- **WHEN** the agent resolves the candidate with `--same-root` issue N
- **THEN** the event becomes an occurrence comment on issue N and no new issue is created
- **AND** a later event with that category is routed directly to issue N

#### Scenario: Open duplicates are consolidated

- **WHEN** `merge-roots` is run with target N and duplicates M1 and M2
- **THEN** N carries the fingerprint markers of M1 and M2 and lists them in a comment
- **AND** M1 and M2 are closed with a comment pointing to N
- **AND** repeating the command changes nothing

#### Scenario: Invalid target

- **WHEN** the named target is closed or is not a router-generated friction issue
- **THEN** the command fails with an error naming the issue and nothing is changed

### Requirement: A merged fix closes the friction records it references

When a pull request is merged, the friction issues referenced by `Fixes-Friction: owner/repo#N` lines in its body or in an OpenSpec `proposal.md` changed by it SHALL be closed with a comment naming the pull request and merge commit. Friction issues without such a reference SHALL NOT be closed automatically. A malformed reference, a reference to another repository or a reference to an issue that is not a router-generated friction issue SHALL fail the run with an error naming the reference.

#### Scenario: Fix references a friction record

- **GIVEN** a merged PR whose proposal contains `Fixes-Friction: lehard/dev-platform#405`
- **WHEN** the close-on-merge run executes for that PR
- **THEN** issue #405 is closed with a comment naming the PR and its merge commit
- **AND** a rerun does not comment again

#### Scenario: No reference

- **WHEN** a merged PR has no `Fixes-Friction:` line
- **THEN** no friction issue is closed

#### Scenario: Reference to a non-friction issue

- **WHEN** a reference names an issue that is not a router-generated friction issue
- **THEN** the run fails with an error naming that reference and closes nothing
