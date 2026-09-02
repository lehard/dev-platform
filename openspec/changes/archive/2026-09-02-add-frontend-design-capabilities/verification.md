# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent-review
Automated-Checks-Evidence: automated-checks.json

The implementation was reviewed against the active proposal, design, delta spec
(`specs/frontend-design/spec.md`), and the accepted `engineering-capabilities`
specification.

## Outcome and success evidence

Opt-in frontend design help is delivered as two canonical descriptors on the #87
lifecycle: `frontend-design` (general) and `high-end-visual-design` (specialized
profile). Both are `instruction-only`, `auto+explicit`, and absent from the
default `dev-platform/capabilities.toml` selection, so no design context, provider
skill surface, or dependency materializes for any project until it explicitly
opts in. No design-specific registry, config, materialization, or update path was
added — `capability_manager.py {list,enable,update,audit,remove,evaluate}` remains
the only lifecycle, and `template/` parity adds only descriptors, pilot fixtures,
and docs.

## Completeness

- **Requirement: Frontend design guidance is an opt-in capability** — descriptors
  + empty default selection + `test_frontend_design_capabilities_are_declared_and_opt_in`.
  Scenario "Unrelated task runs" is backed by the hard-negative backend / data-table
  / settings / migration control cases in `frontend-design-pilot.json`.
- **Requirement: Specialized visual profiles require explicit suitability** —
  `high-end-visual-design` carries a declared non-applicability list and a
  top-of-file applicability gate; `test_high_end_profile_only_materializes_when_a_project_opts_in`
  proves it materializes nothing without opt-in; the dashboard / B2B / regulated
  control cases in its pilot fixture are all `not-trigger`.
- **Requirement: External design skills remain reviewable development tooling** —
  `[provenance]` records source, a pinned 40-char revision, license, and a local
  content hash for each descriptor; no upstream file is vendored; the
  component/treatment map is in `docs/engineering/frontend-design-capabilities.md`.
  `safety_boundary` forbids changing product intent, creating managed work, or
  adding a runtime dependency.

All twelve `tasks.md` items are checked with per-item evidence.

## Correctness

Evidence reviewed:

- `python3 -m compileall -q template/scripts scripts`
- `openspec validate add-frontend-design-capabilities --strict` — valid.
- `python3 scripts/capability_manager.py validate` and `audit` — status ok,
  `enabled: []`, no issues, no unsupported mappings.
- `python3 -m unittest tests.test_capability_manager` (14 tests) — includes the
  four added tests: declaration/opt-in, dependency + pinned provenance,
  opt-in-only materialisation with clean removal, and positive/control fixture
  evidence.
- `python3 scripts/capability_evals.py --json run --fixture
  dev-platform/evals/frontend-design-pilot.json --runtime fixture --runs 3` — 20
  cases, 30 triggered / 30 not-triggered, 0 incomplete, both quality comparisons
  verified.
- `python3 scripts/capability_evals.py --json run --fixture
  dev-platform/evals/high-end-visual-design-pilot.json --runtime fixture --runs 3`
  — 14 cases, 18 triggered / 24 not-triggered, 0 incomplete, both quality
  comparisons verified.
- `python3 scripts/managed_projects.py validate` — registry OK.
- `python3 scripts/run_test_groups.py --all` — 780/780 tests, 13/13 groups
  `success`.
- `python3 template/scripts/check_docs_links.py` — no link/anchor problems.

## Coherence

The capabilities consume the `engineering-capabilities` contract as written
(reproducible/reviewable external content via pinned revision + content hash;
derived provider surfaces; project-owned opt-in). Root and `template/` doc copies
are identical; the new doc is linked from `engineering-capabilities.md`.
`AGENTS.md` shared policy is not forked.

## Known limitation

`tasks.md` item 8's "run a representative UI task" was not executed as a live
provider design task: the shared #79 eval stance keeps live Claude/Codex
triggering `blocked/unavailable` until a supported adapter exists. The generic
AI-UI failure modes and the non-negotiable quality/requirement floor are
enumerated in the instruction files, and the deterministic pilot fixtures encode
the intended trigger boundary as reproducible CI evidence.
