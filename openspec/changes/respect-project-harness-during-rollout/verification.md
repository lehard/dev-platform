# Verification: respect project harness during managed rollout

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review using repository artifacts plus GitHub Platform CI #218

## Completeness

- The v1.4.6 Jara_Fin failure mode is explicitly covered by the change.
- Central rollout validation now branches on the already-authoritative `harness_mode` value.
- Focused regression tests cover both project-owned and platform-owned harness paths.

## Correctness

- Universal rollout validation still checks unresolved rejections, `git diff --check`, platform doctor and version coherence.
- `harness_mode=project` returns after platform-owned validation and never invokes the repository-owned selector.
- `harness_mode=platform` retains the existing `select_checks.py --base origin/<branch> --execute` call.
- This matches the mature-project ownership contract and the generated project-harness CI boundary.

## Coherence

- No downstream project CLI was changed to accommodate the platform.
- Product/application verification remains downstream CI responsibility for project-owned harnesses.
- The change is central rollout tooling only; generated template behavior and project-owned CI are untouched.

## Acceptance evidence

Platform CI #218 passed on head `1d43532da952f6dbe5e1fe8d1ea12b0d131c482e`, including unit tests, strict OpenSpec validation, factory renders, Copier upgrade smokes, mature project harness adoption and project-harness smart-update fallback.

No CRITICAL or WARNING findings remain. Ready for archive and patch release.
