# Verification receipt

Verification-Method: documented semantic OpenSpec review plus automated platform checks
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Semantic review

Reviewed `proposal.md`, `design.md`, all three delta specifications, and the
implemented source/template paths. The default Copier answer remains portable:
it emits no operator configuration. A selected managed-project matrix entry
passes only the boolean `operator_integration` selection into the rollout
command; the private registry is not represented in public source. A selected
render emits the stable environment-backed `[operator]` table, while the
legacy path-backed answer remains supported. Bootstrap only adds the
platform-owned table and rejects incompatible project-owned operator tables.

The rendered task-intake and agent-workflow guidance recognizes either the new
selection or the legacy path selection, preserving requirement-first intake
and the existing ChatGPT-project parity reference. The rollout workflow passes
the matrix flag to the exact-version Copier preparation step; independent
review found the original misplaced environment binding and the follow-up
commit `5b5a4b0` corrected it.

For the requested operator inventory, the private `dev-platform-operator`
registry was updated and pushed at `765ebf9`; its validated matrix contains
only `lehard/planner-agent-lab`, `lehard/Jara_Fin`, and `lehard/cuby` with
`operator_integration: true`.

The Development Backlog Project could not be safely reconfigured through the
available GitHub CLI surface. The exact required manual setting is recorded in
`tasks.md`: in Project #1, make the primary Requirements view exclude the
`type:internal-change` label and retain a separate internal-child view.

## Checks performed

- `python3 -m unittest tests.test_managed_rollout tests.test_platform_bootstrap tests.test_template_contract` — 72 tests passed.
- `python3 scripts/run_test_groups.py --all` — all 13 groups passed; 1,216 declared/discovered tests after reconciling with `origin/main` at `06d55a4`.
- `python3 -m compileall -q scripts template/scripts` — passed.
- `python3 scripts/managed_projects.py validate` — passed.
- `openspec validate enable-operator-managed-requirement-intake --strict --no-interactive` — passed.
- `python3 template/scripts/openspec_lifecycle.py check` — passed before archive readiness.
- `python3 scripts/independent_review.py check enable-operator-managed-requirement-intake` — passed after recording fresh spec-fidelity and engineering-quality reviews for the final candidate `f18547d`. The prior engineering finding was fixed before this receipt.

`openspec verify` is not provided by the installed OpenSpec CLI, so the
documented equivalent semantic review above is the verification method.

OpenSpec-Verify: PASS
