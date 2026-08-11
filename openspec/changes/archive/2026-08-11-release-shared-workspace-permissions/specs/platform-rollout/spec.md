## ADDED Requirements

### Requirement: A delivered shared-workspace permission change is released immutably

After the shared-workspace permission implementation is merged, the platform
SHALL publish it through a new immutable SemVer release and SHALL dispatch
managed rollout using that exact published tag. It SHALL NOT use mutable source
history, move an existing tag, force-push a rollout branch, or auto-merge a
downstream rollout PR.

#### Scenario: Exact-version rollout follows the release

- **GIVEN** the source implementation is merged and a new unused patch version
  is selected
- **WHEN** its release PR changes `VERSION` and GitHub publishes the release
- **THEN** rollout receives the exact immutable release tag
- **AND** each `managed` inventory entry receives a reviewed exact-version
  Copier update PR or an explicit bounded diagnostic
- **AND** `candidate` and `excluded` inventory entries are not mutated
