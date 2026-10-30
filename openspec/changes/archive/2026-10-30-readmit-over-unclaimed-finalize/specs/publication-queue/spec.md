## ADDED Requirements

### Requirement: A developer re-handoff supersedes an unclaimed finalize-pending candidate

The coordinator SHALL accept a fresh developer handoff for a candidate whose latest record is `finalize-pending` when the record is bound to the proven head, the handoff names the same task, the offered finalize job holds no live claim, and the new head descends from the proven head. The accepted handoff SHALL supersede the finalize-pending admission, and an archived managed task whose admitted PR waits in `finalize-pending` SHALL be re-opened for that handoff when the local head strictly descends from the proven head. A live finalize claim, a different task or a head that does not descend from the proven head SHALL be refused with a message naming the reason.

#### Scenario: Reconciled finalize-pending candidate is re-admitted
- **GIVEN** a candidate in `finalize-pending` at its proven head whose finalize job holds no live claim
- **WHEN** the developer hands off a head that merged the moved main on top of the proven head
- **THEN** the handoff supersedes the finalize-pending admission and the candidate re-enters review

#### Scenario: Live finalize claim refuses the re-handoff
- **GIVEN** a candidate in `finalize-pending` whose finalize job is claimed by a live worker
- **WHEN** the developer hands off a descendant head
- **THEN** the handoff is refused naming the claim

#### Scenario: Rewritten head refuses the re-handoff
- **GIVEN** a candidate in `finalize-pending`
- **WHEN** the developer hands off a head that does not descend from the proven head
- **THEN** the handoff is refused naming the missing ancestry
