# Proposal: Align requirement-first intake contract

## Why

The activated requirement-first flow is already represented in AGENTS.md and task-intake.md, but accepted OpenSpec still directs generic fixation to create a managed task and OpenSpec package. Agent surfaces can therefore disagree on a common user instruction.

## Outcome and evidence

All canonical intake surfaces describe Discuss, generic Fix, non-trivial Execute, and explicit direct technical managed paths consistently. A focused automated check fails if the key surfaces return to the old generic-fixation semantics. The direct technical managed path remains available when explicitly requested.

## Scope

Update stale accepted requirements and related agent guidance; add a bounded semantic drift check. The change does not redesign requirement-first flow, transport packages, or managed execution mechanics.

## Current to target

Currently, accepted managed-task-intake and related specs say generic fixation authors a technical package. Target: generic fixation creates/reuses one human-facing Business Requirement and stops. Execution of a Requirement then performs pre-authoring, links internal managed children, and starts them. Explicit technical intent continues to use the direct managed path.
