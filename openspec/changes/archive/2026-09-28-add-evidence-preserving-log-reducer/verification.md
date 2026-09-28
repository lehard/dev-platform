# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of proposal, design, model-routing delta, implementation, regression cases, and exact-recall behavior; `/opsx:verify` is unavailable in this runtime.
Automated-Checks-Evidence: automated-checks.json

The reducer accepts only cold command/test observations. Archive-time source digest, command result, receipt digest/handle, exact UTF-8 byte ranges and quotes are checked before a receipt is returned. A deterministic receipt uses an exact result/error line; an optional routine adapter may submit a semantic receipt. The receipt must be smaller than both the original and hot excerpt. It never writes canonical execution outcome. A bad receipt returns an exact-recall handle; missing or corrupted source reports `source-unavailable` without claiming recoverability.

Checks completed before archive: `python3 -m compileall -q template/scripts scripts`; `python3 scripts/managed_projects.py validate`; `python3 scripts/run_test_groups.py --all` (13 groups, 1390 tests); `python3 template/scripts/openspec_lifecycle.py check`; `python3 -m unittest tests.test_model_routing -q` (108 tests after the final integrity change); `git diff --check`. The dedicated cases cover failing and passing long logs, exact recall, wrong digest, fabricated quote, wrong exit status, low confidence, oversized receipt and source corruption. The final source change after the full suite added source-unavailability and bounded recall provenance, covered by the focused module rerun. No direct provider model launch is part of this provider-neutral reducer core; semantic receipts enter through the optional CLI input.
