# Proposal: Repair process-friction routing integrity

## Why

The newly closed process-health loop still loses source issues before review: the router can create friction issues without the required `process` label, category-based fingerprints fragment one root cause across multiple issues, and the local doctor still advertises a legacy routine review path. The current bounded open-issue scan also must remain correct beyond one API page.

## What Changes

- Make process labeling part of routed issue creation and verification.
- Make duplicate discovery robust to category wording changes and paginated open issue sets.
- Align agent-doctor messaging with weekly cloud review while retaining local recovery surfaces.
- Add bounded reconciliation and end-to-end router-to-review coverage.

## Impact

- Modified specifications: `agentic-maintenance`, `platform-lifecycle`.
- Expected surfaces: `agent_friction.py`, weekly review selection, `agent_doctor.py`, focused process-health tests and docs.
