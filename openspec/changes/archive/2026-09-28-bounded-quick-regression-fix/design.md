## Decision boundary

Use the existing Quick Task lifecycle only when the user requests execution now, the defect is small and bounded, and the expected result is traceable to an already accepted contract. The agent records that contract and the failing case in normal task evidence. A proposed new outcome or materially enlarged repair is not a restoration and uses the existing requirement-first intake path.

## Regression and safety evidence

For a reasonable test seam, first show a failing regression check, then show it passing after repair and rerun the original failure path. Where no reasonable automated seam exists, state that limitation and use an honest reproducer or manual check proportionate to risk. Existing checks, publication, and relevant verification gates remain in force. A quick task does not create an OpenSpec delta or its archive receipt; managed work retains those gates.

## Delivery surfaces

Keep the central `AGENTS.md` bounded. Put detailed criteria in `docs/engineering/task-intake.md` and `agent-workflow.md`, mirror shared contract wording into template docs and the rendered root map, and align ChatGPT Project guidance. Add focused tests that inspect the rendered intake contract and route boundary. Do not add CLI modes, state stores, or release-bundling changes.
