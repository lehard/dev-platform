## 1. Stable identity
- [x] 1.1 Implement shared derivation/allocation and integrate Requirement/child creation, linking, materialization and import without a second registry.
- [x] 1.2 Preserve opaque provenance while adding validated public-safe BR identity and retain old package compatibility.
## 2. Verification
- [x] 2.1 Add meaningful multi-child/retry/conflict/privacy regression coverage and verify template rendering/upgrade inclusion.
- [x] 2.2 Run relevant tests and required platform checks; prepare the implementation for semantic and independent verification.
- [x] 2.3 Complete the child retrospective and prepare the archive/shared-integration handoff.

Required lifecycle gates remain outside the implementation checklist: independent
review, final semantic verification and truthful PASS receipt, archive through
the lifecycle helper, committed archive/spec evidence, and shared Requirement
publication. None is claimed complete by the implementation checkboxes.

## Implementation handoff

Stable identity allocation, intake and additive provenance are implemented.
The dependent child owns branch/PR propagation. DEC-0002 records the approved
public BR-only boundary.

Supervisor verification: 77 intake/identity tests and 92 managed-task tests
passed after review corrections. Earlier host validation passed all 15 test
groups; the archive helper must verify the final candidate and record its
exact automated evidence. Strict OpenSpec validation, Ruff and the private
reference guard passed. Synthetic fresh Copier render and upgrade included
the helper; complete release installation validation passed for the preceding committed
candidate, including all fresh/upgrade cases. Final release CI remains required.

Independent review found pagination, resume, CRLF, historical revision and
sibling-readback, parent-start recovery and cooperating parent-write locking gaps. These have regression coverage and await fresh review.
GitHub has no body compare-and-swap; only observed stale edits or identity
conflicts can be refused. Unobserved concurrent manual body edits are outside
the guarantee. Preserve reservation comments and avoid overlapping edits.

Child retrospective links event 77bff7d72749 for supervisor checks/commit outside
the bounded writer. Final semantic receipt, archive, committed evidence and
shared publication remain pending.
