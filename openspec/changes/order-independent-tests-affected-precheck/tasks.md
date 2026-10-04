## 1. Order independence
- [x] 1.1 Register platform modules in tests through one shared idempotent loader and remove the per-test instance workarounds.
- [x] 1.2 Add a guard that fails on leaked platform module substitution and an isolated/in-group order check for selected groups.
## 2. Affected-group precheck
- [x] 2.1 Implement and test a static direct-reference map from changed Python paths to test modules within canonical groups, with unknown/control-plane paths mapping to nothing.
- [x] 2.2 Run the precheck before the full set in `select_checks.py --execute` so archive/finish use it, aborting early with a failure descriptor.
## 3. Timing decision
- [x] 3.1 Measure per-group wall-clock over comparable runs, identify the slowest groups and record one measurable decision with coverage parity evidence.
## 4. Verification
- [x] 4.1 Demonstrate on a real change touching several template scripts that the full suite finds nothing the precheck would have found.
- [x] 4.2 Run required platform checks, semantic verification and independent review; record truthful verification evidence; archive and commit through the lifecycle helper.
