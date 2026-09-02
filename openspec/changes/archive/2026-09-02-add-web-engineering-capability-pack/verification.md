# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent-review
Automated-Checks-Evidence: automated-checks.json

`/opsx:verify` is not available in this environment, so an equivalent semantic
OpenSpec review was performed across the authored outcome and success evidence,
completeness, correctness, and coherence, against `proposal.md`, `design.md`, the
`engineering-capabilities` delta spec, and the accepted `engineering-capabilities`
specification.

## Outcome and success evidence

- Two independent opt-in capabilities are declared and materialize only when a
  project selects them: `react-next-best-practices` (slim always-loaded index
  plus four bounded topic groups read on demand) and `ui-quality-review`
  (read-only, evidence-backed advisory critic). `capabilities.toml` default
  `enabled = []` is unchanged, and an opt-out project materializes no provider
  surface.
- React/Next stack applicability is a guidance gate, not a dependency change: the
  descriptor `applicability` scopes it to a compatible opted-in React/Next
  codebase and the instruction states it "adds no application runtime
  dependency". Fixture negatives cover Vue, Svelte, jQuery, plain CSS, and
  backend controls.
- The React index declares its four topic-group files as descriptor
  `dependencies`, so `audit` fails if a group is missing rather than silently
  serving partial guidance (covered by a test that unlinks a group).
- `ui-quality-review` findings carry category, location, evidence, severity with
  who is affected, uncertainty, and a smallest-change recommendation; an honest
  "no findings" plus a healthy-checks list is a valid result; the review creates
  no code/Issue/Backlog/managed task, proposes no redesign, and its findings do
  not by themselves block a merge.
- Reproducibility: each descriptor records `content_sha256` of its local
  instruction file (independently authored, nothing vendored), and
  `docs/engineering/engineering-capabilities.md` pins the reviewed references and
  licences (`vercel/next.js` @ `8ea76d64ca3931c1beccceb15d32df5d770f4957`,
  `reactjs/react.dev` @ `24618e2ac310ef03b86e60c858a8dbe55869965d`, W3C WCAG 2.2
  Recommendation 2023-10-05, W3C ARIA APG @
  `7e4034b262bc0d25332e330d8a582aaf34113829`). Adopting newer guidance is an
  explicit `capability_manager.py update`.

## Completeness

Descriptors, instruction files, four React topic groups, two eval fixtures, the
`engineering-capabilities.md` section and provenance table, `test_capability_manager.py`
(four new methods) and `test_template_contract.py` (required-files entries plus a
mirror test) are all present, and every canonical file is mirrored identically
between `dev-platform/` and `template/dev-platform/` (and `docs/` and
`template/docs/`). All eleven `tasks.md` items are complete.

## Correctness

- `openspec validate add-web-engineering-capability-pack --strict --no-interactive` — valid.
- `python3 template/scripts/openspec_lifecycle.py check` — OK.
- `python3 -m compileall -q template/scripts scripts` — OK.
- `python3 scripts/managed_projects.py validate` — OK.
- `python3 scripts/run_test_groups.py --all` — 805 tests, 13 groups, all success.
- `python3 scripts/capability_manager.py validate` / `audit` — status ok with the
  two capabilities declared; `enable` → `audit` ok → `disable` roundtrip is
  idempotent and leaves no derived surface and no `capabilities.toml` diff.
- `python3 scripts/capability_manager.py --json evaluate <id> --fixture
  dev-platform/evals/<id>-pilot.json --runtime fixture` for both capabilities:
  20 cases, 20 passed, 0 failed, 0 incomplete, 30 triggered / 30 not-triggered,
  both objective quality comparisons `improved`.
- `capability_manager.py eval-decision --change-kind new --runtime fixture` →
  `run` (bounded deterministic fixture), matching the lifecycle contract.

## Coherence

The capabilities reuse the existing provider-neutral descriptor/opt-in/derived-
skill lifecycle exactly as `frontend-design`, `systematic-bug-diagnosis`, and
`selective-domain-interrogation` do. No second capability registry, planning
lifecycle, router, or AGENTS.md fork is introduced; the docs stay in the shared
`engineering-capabilities.md`; Claude/Codex live triggering remains explicitly
`unsupported` and the deterministic fixture is labelled as CI evidence, not a
live provider claim.
