## ADDED Requirements

### Requirement: Detection-only delegated writers accept a recorded integration advance

Every platform fast-forward of the integration checkout's main branch SHALL append an integration-advance receipt naming before and after heads, the recorded remote-tracking main, the acting worktree, tool and time. For a detection-only delegated writer the platform SHALL classify integration-head movement as a verified concurrent advance only when no integration path was created, changed or disappeared, the new head is a fast-forward descendant equal to the recorded remote-tracking main, and an unbroken receipt chain from the pre-run head to the new head exists whose every acting worktree is outside the delegated worktree. The raw observation SHALL be preserved beside the classification. Missing, broken, malformed or self-attributed evidence SHALL remain a containment violation. A historical false violation recorded before receipts existed MAY be recovered only through an evidence-bound recovery tied to the exact friction event, the route's open delegation timing and the remote-tracking reflog.

#### Scenario: Sibling merge during a Claude delegation

- **GIVEN** a Claude delegation is open
- **AND** another task's finish fast-forwards integration main to the recorded remote-tracking main and writes a receipt
- **WHEN** the supervisor records the execution
- **THEN** the execution is recorded with a verified concurrent advance and the raw head movement

#### Scenario: Unproven movement

- **WHEN** a path changed, the move is not a fast-forward, the head differs from remote-tracking main, a receipt is missing or the chain names the delegated worktree
- **THEN** recording fails as a containment violation

#### Scenario: Historical false violation

- **GIVEN** a Claude delegation failed recording because of a pure head move before receipts existed
- **WHEN** recovery is requested with the exact friction event and heads proven by the remote-tracking reflog within the delegation window
- **THEN** a recovery record is stored without creating an execution
- **AND** later recording classifies any further movement only through receipts

## MODIFIED Requirements

### Requirement: Verified concurrent integration advancement is distinct from a delegated escape

The platform SHALL retain raw observation of integration `HEAD` movement during
a delegated write, but it MAY classify a pure head movement as a verified
concurrent integration advance rather than a containment violation only when
the writer had native hard containment or detection-only movement was verified
under "Detection-only delegated writers accept a recorded integration advance",
no integration path was created,
changed or disappeared, the new head is a fast-forward descendant of the
pre-run head, and it exactly equals the integration checkout's recorded
remote-tracking base-branch ref. The routing execution receipt SHALL preserve
the before/after heads and explicit classification.

All other integration-head movement, including detection-only execution not verified
under "Detection-only delegated writers accept a recorded integration advance",
non-fast-forward movement, unverified/missing remote refs, or any path-level
change, SHALL remain a containment violation.

#### Scenario: Another lifecycle fast-forwards clean integration during a native child run

- **GIVEN** a native hard-contained delegated writer runs in its assigned
  worktree
- **AND** the integration snapshot has no new, changed or disappeared paths
- **AND** a separate lifecycle fast-forwards integration from the pre-run head
  to the exact recorded remote-tracking base-branch head
- **WHEN** the delegated writer returns successfully
- **THEN** the execution records a verified concurrent integration advance
- **AND** the routing outcome is not marked as a delegated escape

#### Scenario: Head movement cannot be proven as a concurrent remote fast-forward

- **GIVEN** a delegated writer observes integration-head movement
- **WHEN** a path changed, the move is not a fast-forward, the remote ref does
  not exactly match, or containment is neither native hard nor detection-only
  verified under "Detection-only delegated writers accept a recorded integration advance"
- **THEN** the containment result remains failed
- **AND** normal friction recording remains available for the violation
