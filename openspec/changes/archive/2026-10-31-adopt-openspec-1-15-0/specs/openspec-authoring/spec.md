## ADDED Requirements

### Requirement: The requirement length limit is enforced without exemption

Platform validation SHALL run `openspec validate --all --strict` on the pinned OpenSpec release with no repository filter or exemption for the requirement length warning, so every requirement description in the main specs and in ADDED delta requirements stays at 500 characters or fewer.

#### Scenario: An overlong requirement fails platform validation

- **WHEN** a main spec or an ADDED delta requirement has a description over 500 characters
- **THEN** `openspec validate --strict` on the pinned release fails
- **AND** no platform gate filters out that warning
