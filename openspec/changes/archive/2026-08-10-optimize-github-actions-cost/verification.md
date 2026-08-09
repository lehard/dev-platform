# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent manual semantic review across completeness, correctness, and coherence, plus local platform validation.

## Completeness

- Generated CI renders PR/manual for `publish_mode=pr` and main-push/manual for `publish_mode=direct`, with cancellation of superseded runs.
- Central CI runs shared checks once while retaining light, standard, and multi-agent smoke coverage.
- Release publication and rollout remain side-effect workflows without cancellation.
- Reviewed project-owned PRs were created for Jara_Fin (#8), planner-agent-lab (#13), and etsy (#4). Cuby remains in the managed rollout matrix; candidates/excluded repositories remain non-mutating.

## Correctness

- `python3 -m compileall -q template/scripts scripts`, registry validation, 101 unit tests, lifecycle hygiene, strict OpenSpec 1.6.0 validation, PR/direct render inspection, Copier upgrade smokes, project-harness acceptance, and guarded-recopy smoke passed.
- The cost record is: Jara_Fin automatic triggers 3 to 1 (PR), planner `quality.yml` 2 to 1 (PR), and Etsy CI 2 to 1 (PR); Jara's full suite remains manual and Etsy Ruff moves from macOS to Linux. The legacy planner CI was retained because private-repository protection/ruleset metadata is unavailable on GitHub Free.

## Coherence

- Template behavior, central CI, documentation, tests, proposal, design, and delta spec agree on local-heavy/cloud-final verification and project CI ownership.
- The rollout repair discovered during validation is tracked in the separate `stabilize-copier-task-execution` change rather than silently expanding this contract.
