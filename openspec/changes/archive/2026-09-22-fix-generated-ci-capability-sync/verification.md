# Verification: Materialize selected capability surfaces before platform_doctor.py in generated CI

## Method

`/opsx:verify` was not available in this execution environment. Performed the documented equivalent manual OpenSpec semantic review: re-read `proposal.md`'s Why/What Changes/Success Evidence, `design.md`'s root-cause analysis, and the `engineering-capabilities` spec delta's ADDED requirement with its two scenarios, then checked the one-line CI implementation and the three new tests against each.

## Root cause confirmation

Before writing this change: reproduced the real failure (`lehard/Jara_Fin`'s `Roll Out Platform` dispatch left an unresolved `.github/workflows/dev-platform.yml.rej`), then read `template/scripts/capability_manager.py`'s `derived_path()`/`audit()`, `template/scripts/platform_doctor.py`'s `check_engineering_capabilities()`, and `template/.gitignore.jinja` directly to confirm the exact mechanism (gitignored derived surfaces + no `sync()` before `audit()` in generated CI). Confirmed via `git log --oneline` and direct inspection of `dev-platform`/`lehard/cuby`/`lehard/planner-agent-lab`/`lehard/Jara_Fin`'s own `dev-platform/capabilities.toml` and `.claude/skills` state that this is a genuine, generic gap masked by three different reasons in three different projects, not a Jara_Fin-specific customization.

## Success evidence review

- "A real Copier render with capabilities enabled reproduces the failure and its fix" — reproduced directly: fresh render, hand-set `enabled = [...]`, `platform_doctor.py` exit 1 with the exact "derived provider surface is stale or missing" message before the fix's step sequence; exit 0 after running it.
- "Materialized surfaces remain untracked" — confirmed via `git init` + `git add -A` (no skill files staged) and `git check-ignore -v` on the specific materialized paths.
- "Full-tree diff shows exactly one new step in exactly one file" — confirmed against the unfixed parent commit's render with identical inputs.

## Spec-delta scenario review

- "A fresh checkout has capabilities enabled" — this is exactly the reproduced failure/fix.
- "Materialized surfaces are never committed" — confirmed via `git check-ignore`; no new step stages or commits them.

## Independent review

A native Claude executor (general-purpose subagent) independently read the proposal/design/spec and the full diff, verified the root-cause chain itself by reading the same three source files directly, and ran its own live reproduction: rendered fresh via `copier copy --trust --defaults --skip-tasks` (needed `--skip-tasks` only because this sandbox's `shared_workspace` group-permission preflight fails on `/tmp`, unrelated to this fix), reproduced the exact failure and fix, confirmed the gitignore behavior, confirmed `sync()` is a safe no-op for the default empty selection, full-tree-diffed HEAD vs. the parent commit (exactly one file, exactly the new step), ran `tests.test_capability_manager`/`tests.test_template_contract` (74 passed) and the full suite (`run_test_groups.py --all`: 13/13 groups, 1145 tests) plus strict OpenSpec validation. It reported no code-correctness findings; its one "should-fix" was that the OpenSpec verify/archive lifecycle steps were still pending at review time (expected — this receipt and the subsequent archive complete them) and it flagged the `lehard/planner-agent-lab` committed-surfaces claim as unverified external context that does not affect this template-only fix's correctness.

## Tests run

```
python3 -m compileall -q template/scripts scripts
python3 -m unittest tests.test_capability_manager tests.test_template_contract -v   # 74 passed
python3 scripts/run_test_groups.py --all        # 13/13 groups passed, 1145 tests
openspec validate fix-generated-ci-capability-sync --strict   # valid
```

Plus the real-Copier-render verification described above, independently repeated by the reviewing agent with matching results.

No unresolved finding remains.

OpenSpec-Verify: PASS
Verification-Method: manual-semantic-review (opsx:verify unavailable in this environment)
Automated-Checks-Evidence: automated-checks.json
