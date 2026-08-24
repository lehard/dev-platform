# Verification: Add experimental DeepSeek Harness runtime adapter

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review plus platform regression, rendered-template, and bounded smoke checks
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Compared the implementation to every added `agent-runtime` requirement: the backend is optional and disabled by default, exact-version gated, subordinate to the managed lifecycle, and confined to an adapter plus private runtime profile.
- Confirmed the observation profile mounts no write-capable tools and `workspace-write` refuses before process launch because the pinned SDK cannot attest sandbox enforcement. Session state must resolve inside the assigned workspace, and the smoke snapshots the integration checkout before and after execution.
- Confirmed terminal result, cancellation, process-group cleanup, platform timing, and complete authoritative DSH usage samples use the canonical runtime-neutral `execution.efficiency` vocabulary from `lehard/dev-platform#312`. Partial, malformed, unsupported, and aggregate identities remain `unknown`; the adapter retains no competing usage schema or execution database.
- Confirmed no task-intake, OpenSpec lifecycle, routing-policy, verification, publication, rollout, or native Codex/Claude default semantics were replaced. DSH Agent Teams, skills migration, comparative evaluation, automatic switching, and automatic upstream promotion remain excluded.
- Confirmed the exact pinned update procedure requires compatibility tests, bounded smoke, normal immutable release, and rollout before downstream behavior may change.

## Executed evidence

- `openspec validate add-deepseek-harness-runtime-adapter --strict --no-interactive` — PASS.
- `python3 -m unittest tests.test_model_routing tests.test_deepseek_harness_runtime tests.test_template_contract` — PASS (86 tests).
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `python3 scripts/managed_projects.py validate` — PASS (3 managed projects, 7 candidates, 3 excluded).
- `python3 scripts/run_test_groups.py --all` — PASS (13 groups; full declared coverage, 716 tests, no missing or duplicated tests).
- `python3 template/scripts/openspec_lifecycle.py check` — PASS before the final task checkbox was completed.
- Copier render smoke from committed `HEAD` — PASS; the rendered project contains the adapter, shared model-routing schema, private profile, exact requirements pin, and runtime guide, and its capability entrypoint remains disabled by default.
- `python3 scripts/deepseek_harness_adapter.py capability` and `smoke --enable-experimental` — explicit capability BLOCKED on `darwin/x86_64` because the pinned upstream runtime has no supported wheel for that host. This is the accepted host-capability outcome; no live-runtime success is claimed.
