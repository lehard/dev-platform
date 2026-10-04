# Tasks

- [x] Add the card claim to `requirement_intake.py start` after durable state init, with the failure semantics in design.md.
- [x] Reconcile the card at the entry of `execute_requirement.advance` so resume repairs a `Ready` card before slow steps.
- [x] Add regression tests: card is `In progress` before any later pre-authoring stage; a second agent reading the card during first agent's preparation sees `In progress`; rerun is idempotent; reconcile failure keeps state and never writes `Ready`.
- [x] Update `docs/engineering/task-intake.md` and the agent-workflow spec; run required platform validation, semantic verification, archive and publication.
