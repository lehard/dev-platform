# Semantic verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent independent supervisor review of the committed implementation against the active proposal, design, delta specification, current completion lifecycle, and generated-template distribution.
Automated-Checks-Evidence: automated-checks.json

## Outcome and completeness

The committed implementation adds a provider-neutral `independent_review.py`
surface that prepares exact candidate-bound requests, records one report per
required perspective, and validates both reports. The active completion
lifecycle calls that gate before a PASS receipt can become archive-ready when
the opt-in configuration is enabled for a managed change. The receipt marker
keeps accepted review evidence visible without adding a second lifecycle.

Both required perspectives are present in the request contract. The generated
template, central source adapter, doctor, adoption collision checks, check
registry, and central/template workflow documentation were updated together.

## Correctness and coherence

The request/report schema binds review evidence to request id, resolved base
and candidate SHAs, and binary diff SHA-256. Record and readiness validation
recompute that identity, so a new candidate or base rejects stale evidence.
Unavailable review and blocker-status material findings fail readiness;
`fixed` and explicitly reasoned `rejected` findings are accepted. Quick and
unmanaged work remains outside the opt-in gate. The review helper neither
launches a provider nor exposes publication, Project, archive, or completion
actions, so review remains evidence-only.

No material findings remained after the supervisor review. The lack of a
provider launch is intentional: selecting or operating a review runtime is a
documented non-goal, while the request/report boundary remains replaceable.

The first archive attempt exposed an **introduced** compatibility defect: a
minimal/legacy checkout could contain the updated lifecycle without the new
helper module, so import failed before the lifecycle's existing safety checks.
The final implementation retains compatibility only while review is disabled
(the default), and fails closed with a repair instruction if that checkout
explicitly enables independent review. The targeted publication/lifecycle
regressions covering this path pass after the repair.

## Checks actually run before archive

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 -m unittest tests/test_independent_review.py tests/test_openspec_lifecycle.py tests/test_adopt_project.py tests/test_central_dogfood_lifecycle.py tests/test_template_contract.py` — 86 passed before the compatibility repair.
- `python3 -m unittest tests/test_openspec_lifecycle.py tests/test_independent_review.py tests/test_git_lifecycle.py tests/test_merge_lifecycle_resilience.py tests/test_protected_main_zero_handoff.py tests/test_publication_recovery_cli.py` — 65 passed after the repair.
- `openspec validate add-independent-verification-perspectives --strict --no-interactive`
- `python3 template/scripts/openspec_lifecycle.py check`

Archive will run the selected platform checks and write the referenced
`automated-checks.json`; that file is the authoritative record of its executed
commands.
