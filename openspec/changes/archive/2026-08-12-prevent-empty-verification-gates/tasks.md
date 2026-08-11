## 1. Reproduce and map current behavior

- [x] 1.1 Reproduce the `dev-platform#39` class with a platform-owned fixture whose affected check group resolves to an empty command list.
- [x] 1.2 Trace selection, execution, doctor and OpenSpec verification/archive surfaces to identify where empty and passed states are currently conflated.
- [x] 1.3 Confirm the change does not conflict with the current `harness_mode=project` ownership contract.

## 2. Add truthful check-state semantics

- [x] 2.1 Make platform-owned selection/execution expose command count and applicability/result state deterministically.
- [x] 2.2 Treat an applicable required empty group as a blocking configuration error for `harness_mode=platform`.
- [x] 2.3 Preserve a distinct `not applicable` state so intentionally unrelated changes are not blocked merely because no command was selected.
- [x] 2.4 Ensure compilation/syntax evidence is not described as product-test coverage where the reviewed platform-owned contract expects a separate test command.

## 3. Wire completion/verification truthfulness

- [x] 3.1 Surface invalid empty coverage in doctor/lifecycle before semantic PASS/archive.
- [x] 3.2 Ensure verification evidence reports the actual executed commands and cannot cite automated checks that never ran.
- [x] 3.3 Preserve project-owned harness behavior and existing project CI authority.

## 4. Regression and delivery

- [x] 4.1 Add regressions for empty applicable group, non-empty passing/failing group, genuinely non-applicable scope and project-owned harness.
- [x] 4.2 Run full platform, template/render/Copier and OpenSpec validation applicable to the touched surfaces.
- [x] 4.3 Record truthful semantic verification, archive through the lifecycle helper and publish/roll out through the ordinary immutable release path if runtime/template behavior changes.
