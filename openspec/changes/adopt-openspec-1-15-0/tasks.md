## 1. Split
- [x] 1.1 Split the long requirements of lifecycle-workers, publication-queue and chat-coordinator by the upstream procedure.

## 2. Version bump
- [x] 2.1 Move every recorded copy of the tested OpenSpec version to 1.15.0 (template config, four workflows, README, test pins).
- [x] 2.2 Add exact-CLI regression fixtures for the strict length limit and dropped delta text; show them pass on 1.15.0 and fail on 1.13.2.
- [x] 2.3 openspec-authoring: length limit enforced without exemption.

## 3. Verification
- [x] 3.1 `openspec validate --all --strict` on 1.15.0 after a simulated archive; full validation; semantic review of meaning preservation; adoption smoke with the new pin.
