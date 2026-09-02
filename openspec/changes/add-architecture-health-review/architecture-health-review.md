# Architecture Health Review — 2026-09-02

- target repository: `lehard/dev-platform`
- exact revision: `35cec712d25b1f6316cd7b97e0562accf4dff9eb`
- reviewed scope: optional engineering capability lifecycle and central-source/template adapter boundary; excluded application-domain architecture, GitHub state, and uncommitted task changes
- evidence gathered: `git show 35cec712d25b1f6316cd7b97e0562accf4dff9eb:<path>`, `git log --oneline -12`, `docs/engineering/engineering-capabilities.md`, `scripts/source_adapter.py`, `template/scripts/capability_manager.py`, `tests/test_capability_manager.py`, and `tests/test_template_contract.py`

## Observations

### AH-001 — The source adapters are a healthy seam, not pass-through architecture debt

- category: seam
- locations: `scripts/source_adapter.py:1-25`, `scripts/capability_manager.py:1-4`, `template/scripts/capability_manager.py:1-10`
- observation: central entrypoints deliberately delegate to the template implementation through one source adapter. The adapter establishes the source-root and template-script lookup, then runs the shared implementation; individual wrappers expose no lifecycle policy of their own.
- evidence: `scripts/source_adapter.py:3-6` documents that the central repository is intentionally not rendered from its Copier template and that the adapter runs the same authoritative lifecycle primitives released to managed projects. `template/scripts/capability_manager.py:129-135` hash-checks instruction provenance, and `:253-304` owns capability materialization/audit policy. Moving that policy into every source wrapper would duplicate it across the launcher surface.
- confidence: high

### AH-002 — Adding a canonical capability crosses an explicit multi-file registration seam

- category: locality
- locations: `dev-platform/capabilities/`, `template/dev-platform/capabilities/`, `tests/test_capability_manager.py:36-41`, `tests/test_template_contract.py:14-16`
- observation: a new capability must be represented in both central and template trees, while the unit-fixture setup and required-template list name known files explicitly. This review itself must touch all four locations to make a new descriptor available and testable.
- evidence: the capability contract names `dev-platform/capabilities/<id>.toml` as canonical and requires a hash-checked sibling instruction (`docs/engineering/engineering-capabilities.md:5-9`; `template/scripts/capability_manager.py:126-135`). At the reviewed revision, test setup copied the known capability pairs explicitly and the template contract enumerated required files.
- confidence: medium

## Uncertainty and counter-evidence

- The two-tree duplication is a documented consequence of central source not rendering itself from Copier, and the explicit test lists can intentionally make platform-owned additions visible. No change history was inspected to quantify missed registrations, so the observation is not evidence that current maintainers are making errors.
- AH-001 is the healthy control: despite a thin wrapper, the deletion test says the shared source/template coordination complexity would reappear across callers if the adapter were removed. It is therefore not an advisory refactor candidate.
- No runtime architecture, downstream Copier-update project, or untrusted external capability was reviewed.

## Advisory improvements

- AH-002 is worth exploring only if capability additions repeatedly miss a mirrored location. A human could evaluate a manifest- or discovery-based parity check that preserves deliberate review visibility while reducing registration locality. The candidate must prove that it does not silently broaden the descriptor set or weaken source/template ownership; no managed task is created by this report.

## Optional alternative designs

- trigger: not requested. No high-consequence interface, cross-subsystem ownership boundary, durable data contract, or costly-to-reverse integration was explicitly marked for comparison.

## Promotion boundary

No code, Issue, Backlog item, managed task, commit, or publication was created by this review. A human may promote an accepted candidate through the normal Discuss/Backlog/OpenSpec task-intake lifecycle.
