## ADDED Requirements

### Requirement: Reviewed Jara exact-head migration adapts its known regression surface

When a reviewed Jara project-owned publication harness requires an exact-head
compatibility migration, Dev Platform SHALL also adapt the known reviewed
regression test surface that strictly mocks that publication behavior. Both
surfaces SHALL be selected only by exact reviewed bytes and a rerun SHALL
prove the generated state by reconstructing those bytes. Unknown or partial
project-owned test drift SHALL block without writing either surface.

#### Scenario: Known Jara strict mocks receive exact-head responses

- **GIVEN** Jara's reviewed legacy test source and publication harness
- **WHEN** rollout applies the exact-head migration
- **THEN** the strict mocks return a local branch head and one matching exact
  PR record
- **AND** Jara's merge-policy and cleanup regressions remain asserted
- **AND** the resulting Jara CI is eligible to pass without manual edits.

#### Scenario: Unknown Jara regression-test drift is encountered

- **WHEN** the companion test source differs from both the reviewed legacy
  and reversibly generated forms
- **THEN** rollout fails closed before modifying the harness, helper, or test.
