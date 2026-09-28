## ADDED Requirements

### Requirement: Concrete model bindings change as policy only

Concrete provider-local model bindings SHALL be changed only in the replaceable routing policy (`[model_routing]` and its template and built-in default mirror) and SHALL NOT alter routing tiers, assurance, verification policy, the routing/execution provenance schema or the lifecycle. Only stable, production-eligible models SHALL become a production default; a prerelease, beta or RC model SHALL NOT. A binding change SHALL reach managed projects only through the existing immutable release and template update path, and SHALL be reversible by restoring the previous binding through that same path. Historical routing records naming a superseded model SHALL remain readable and be calibrated under their recorded model.

#### Scenario: A newer stable model replaces a superseded binding

- **GIVEN** a superseded model is bound to a tier
- **WHEN** a newer stable model is adopted for that tier
- **THEN** only the policy value changes
- **AND** the authored start tier, assurance and verification requirements of every task are unchanged

#### Scenario: A regression requires rollback

- **GIVEN** a new binding shows a regression in recorded calibration evidence
- **WHEN** the previous binding is restored and released
- **THEN** managed projects return to it through the normal template update without per-project edits
