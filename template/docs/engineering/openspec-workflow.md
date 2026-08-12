# OpenSpec workflow

OpenSpec is the planning contract for non-trivial product and architecture changes. It complements repository process rules and project-specific verification.

## Contract model

Do not model these as a flat precedence ladder:

1. `AGENTS.md` constrains **how work may be performed**.
2. `openspec/specs/` states the **accepted current behavior**.
3. `openspec/changes/<active>/` states the **approved delta** currently changing that behavior.
4. Code implements current behavior plus approved active deltas.

The target behavior during an active change is therefore `current specs + active delta`, subject to process/safety constraints.

## No silent divergence

If implementation reveals that the plan must change, update the relevant artifact before proceeding in a different direction:

- intent/scope -> `proposal.md`;
- observable behavior -> delta specs;
- technical approach -> `design.md`;
- execution order/dependencies -> `tasks.md`.

Do not knowingly make code and OpenSpec disagree and plan to repair the docs later.

## Verify, archive, then publish

For non-trivial changes:

`plan review -> implementation -> project tests/QA -> semantic OpenSpec verify -> verification receipt -> archive -> publish`

Prefer `/opsx:verify` when the installed agent integration exposes it. If the current environment cannot invoke that workflow, OpenSpec allows the agent to re-read the change and implementation and perform the equivalent review. The equivalent review must cover the same three dimensions: **completeness, correctness, and coherence**.

Semantic verification and `openspec validate` are different. The former checks implementation against intent; the latter checks OpenSpec structure. Neither replaces project-specific tests, E2E, browser/render QA, migrations or operational checks.

After material semantic findings are resolved, record the result in the active change's `verification.md` with:

```text
OpenSpec-Verify: PASS
Verification-Method: <method actually used>
```

The report should state what was checked and any warnings/suggestions that remain. For a platform-owned harness, it must also contain:

```text
Automated-Checks-Evidence: automated-checks.json
```

The archive helper creates that file from the selected commands it actually runs, then refuses to archive if the selection is empty/invalid, any command fails, or the receipt does not cite the generated evidence. This is intentionally not required for `harness_mode=project`, where repository CI remains the product-verification authority.

Then archive through the platform entrypoint:

```bash
python3 scripts/openspec_lifecycle.py archive <change>
```

The helper requires all tasks to be complete and the PASS receipt plus method, runs strict validation, invokes the OpenSpec CLI archive, and validates the resulting OpenSpec state. It does not emulate semantic verification and does not install or upgrade OpenSpec.

`finish_task.py` and CI run lifecycle hygiene. If all task checkboxes in an active change are complete but the change is still active, publication is blocked. This turns “remember to archive” into a repository invariant rather than a human reminder.

Where `/opsx:verify` is the selected method, the expanded OpenSpec verify workflow must be enabled for the repository (`openspec config profile`, then `openspec update`). `platform_doctor.py` detects whether that generated workflow is present, but absence is not a reason to skip semantic verification: use the documented equivalent review if the current agent surface cannot invoke it.

## OpenSpec version policy

`.dev-platform.toml` records the platform-tested OpenSpec version and minimum compatible version. `platform_doctor.py` warns when the local CLI is newer than the tested version and fails when it is below the minimum. The platform does not silently upgrade a user's global CLI.
