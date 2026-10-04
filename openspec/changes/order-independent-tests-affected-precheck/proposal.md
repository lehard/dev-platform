## Why
In BR-341 the full suite (11–14 min) ran three times at archive plus at release, and 8 broken tests were first found at the final archive. Two failed only inside their group because test modules replace `sys.modules` entries for platform modules (`managed_task`, `requirement_integration`, ...), so patched objects and caught exception classes belong to a different module instance than the code under test. Six more would have been visible immediately by running the affected group. Today every `scripts/**`, `template/scripts/**` or `tests/**` change is a full-suite trigger, so there is no supported fast path for platform code at all.

## What Changes
- Remove order dependence caused by test-time `sys.modules` substitution in the known modules and add a guard that fails on direct `sys.modules` registration in tests or on a duplicate module instance across forward and reverse import order.
- Add a supported, opt-in affected-test precheck: map changed Python paths to the test modules that directly reference them inside their canonical groups, run those first, and stop before the full suite when they fail. The precheck is early feedback only, recorded separately, and never replaces the full/protected set.
- Run the precheck automatically in the archive/finish validation path before the full suite.
- Measure full-suite wall-clock per group, identify the longest groups and record one measurable speed decision (split, rebalance, or no change) with before/after evidence of identical mandatory coverage.

## Capabilities
### Modified Capabilities
- `platform-ci`: test groups are order-independent and guarded against module substitution leaks; full-suite timing evidence is recorded.
- `platform-lifecycle`: an affected-group precheck precedes full validation for full-trigger platform paths.

## Impact
`tests/**` fixtures for the listed modules, `scripts/run_test_groups.py`, `template/scripts/select_checks.py`, `dev-platform/checks.toml`, archive validation call in `template/scripts/openspec_lifecycle.py`. Downstream projects keep their existing selection unless they configure a mapping.

## Outcome and Evidence
A selected group passes both in isolation and inside its group; the guard fails on a deliberately leaked substitution. On a real task changing several template scripts the precheck runs first and the subsequent full suite finds nothing the precheck would have found. Timing evidence names the slowest groups and the decision's measured effect.

## Non-goals
No change to the review/repair/integration lifecycle (BR-353). No skipping or caching of the mandatory full suite before merge or release. No wholesale test rewrite where removing the substitution suffices.
