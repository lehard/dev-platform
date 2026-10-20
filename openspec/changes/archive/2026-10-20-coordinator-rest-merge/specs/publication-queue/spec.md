## ADDED Requirements

### Requirement: Coordinator merge is a REST merge with an expected-head guard

The coordinator SHALL request the protected merge of a candidate through the GitHub REST merge endpoint with the squash method and the expected head commit, so that GitHub itself evaluates branch rules, ruleset bypass for the coordinator App and required checks. It SHALL NOT use a client that refuses on its own reading of the merge state, SHALL NOT request an administrator override or auto-merge, and SHALL report a refused merge as a waiting outcome with a bounded reason and no merge.

#### Scenario: Ruleset-protected main with App bypass

- **GIVEN** a green candidate whose base ref is restricted by a ruleset that the coordinator App may bypass for pull requests
- **WHEN** the coordinator requests the merge
- **THEN** it calls the REST merge endpoint with `merge_method=squash` and `sha` equal to the expected head
- **AND** a successful response leads to the merged transition after the merged fact is read back

#### Scenario: Merge refused

- **WHEN** the REST merge endpoint refuses (head changed, rule or required check)
- **THEN** the candidate stays waiting with the bounded refusal reason
- **AND** no administrator override, auto-merge or alternate merge call is attempted
