## Why

The current quick-work rule allows small bounded changes but does not explicitly say that a repair restoring already accepted behavior stays quick. An earlier one-line regression repair incurred a full Requirement and OpenSpec package. The rule needs a clear boundary so repair evidence is preserved without treating restoration as a new product contract.

## What Changes

- Clarify the existing quick path for directly requested, small regression repairs whose expected behavior is unambiguously established by an accepted spec or equivalent durable contract.
- Require proportionate regression evidence: demonstrate the defect before repair and pass after, rerun the original failure path, or document why no reasonable test seam exists.
- Keep applicable safety, check, publication, and verification gates. If evidence exposes new behavior, architecture, compatibility, data contract, or material scope, stop quick implementation and enter requirement-first intake before further work.
- Update central and rendered agent/intake guidance and the accepted managed-task-intake spec; add focused contract coverage. Do not introduce a new task lifecycle or change release-bundling policy.

## Impact

The change affects process guidance and its rendered template, the accepted intake contract, and focused checks. It does not relax managed provenance for active OpenSpec work or existing terminal publication safeguards.
