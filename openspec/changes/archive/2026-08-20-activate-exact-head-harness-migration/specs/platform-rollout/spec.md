## ADDED Requirements

### Requirement: Compatibility migration activates before a project harness CLI guard

When a managed project-owned publication harness matches a reviewed legacy
compatibility predicate, Dev Platform SHALL install the exact-head publication
implementation before the script's effective CLI entrypoint. A migration SHALL
NOT rely on definitions that execute only after `if __name__ == "__main__"`.
The migration SHALL preserve repository-specific orchestration outside the
bounded publication surface and SHALL fail closed without writing unrecognized
or structurally ambiguous harness bytes.

#### Scenario: Jara-like harness is invoked as a CLI after migration

- **GIVEN** a reviewed Jara-like harness has an old merged PR for branch X at
  head A and a current reused branch X at head B
- **WHEN** its migrated script is run through Python's CLI entrypoint
- **THEN** the exact-head publication implementation is active before `main()`
- **AND** PR A cannot authorize terminal success, remote deletion, or board
  cleanup for B
- **AND** board/worktree/serialized orchestration remains intact.

#### Scenario: Planner-like harness is invoked as a CLI after migration

- **GIVEN** a reviewed Planner-like harness is migrated
- **WHEN** the script is invoked through its real CLI entrypoint
- **THEN** exact PR identity and exact merge confirmation are active before
  `main()`
- **AND** standalone integration-clone orchestration remains intact.

#### Scenario: Unknown or ambiguous project harness is encountered

- **WHEN** its source fingerprint or CLI guard shape differs from a reviewed
  migration predicate
- **THEN** rollout fails with a compatibility diagnostic
- **AND** it does not write the helper or modify harness bytes.
