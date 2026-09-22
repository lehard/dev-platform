# Design: Materialize selected capability surfaces before platform_doctor.py

## Root cause, confirmed empirically (not assumed from the Jara_Fin conflict alone)

The user's own hypothesis was verified before writing any fix:

1. Read `template/scripts/capability_manager.py`'s `derived_path()`: materialized skill files live at `.{provider}/skills/dev-platform-{id}/SKILL.md`.
2. Read `template/.gitignore.jinja`: lines 4-5 explicitly ignore `.codex/skills/dev-platform-*/` and `.claude/skills/dev-platform-*/`.
3. Read `template/scripts/platform_doctor.py`'s `check_engineering_capabilities()`: it runs `capability_manager.py --json audit` and fails the whole doctor run if `payload["status"] != "ok"`.
4. Read `capability_manager.py`'s `audit()`: for each enabled capability, if its derived path `is_file()` is false, it appends `"derived provider surface is stale or missing: <path>"` to `issues`, making `status == "error"`.
5. Read `template/.github/workflows/dev-platform.yml.jinja`: confirmed zero references to `capability_manager.py` anywhere in the file before this change.
6. Reproduced live: `copier copy --trust --defaults` a fresh project, hand-edited `dev-platform/capabilities.toml` to enable two capabilities (matching Jara_Fin's real selection), ran `python3 scripts/platform_doctor.py` -- exit 1, `"optional engineering capability audit failed"`, listing the exact `.claude/skills/...`/`.codex/skills/...` paths as missing.
7. Confirmed this is not project-specific: `dev-platform`'s own `dev-platform/capabilities.toml` has `enabled = []` (never exercises this path); `lehard/cuby`'s selection is also empty; `lehard/planner-agent-lab` has its derived skill directories anomalously **committed** to git (`gh api .../contents/.claude/skills` lists them), which is itself a drift from the platform's own gitignore contract, not a template worth matching. `lehard/Jara_Fin` is the one project with non-empty capabilities that also correctly follows the gitignore contract (no committed derived surfaces), which is exactly why it alone needed a local workaround.

## Fix

Add one step to `template/.github/workflows/dev-platform.yml.jinja`, immediately before "Validate platform contract":

```yaml
      - name: Materialize selected capability surfaces
        run: |
          umask 0002
          python3 scripts/capability_manager.py sync
```

This mirrors the fix Jara_Fin already validated in production (PR #81, "fix(ci): materialize selected capability surfaces"). `umask 0002` matches this codebase's own established `cooperative_umask()` convention (`template/scripts/_platform_common.py`) for files that may later be read across a shared workspace; it is a harmless no-op on an ephemeral single-user GitHub Actions runner.

Confirmed safe to run unconditionally for every generated project (light/standard/multi-agent, any harness_mode): `template/dev-platform/capabilities/*.toml` (the canonical descriptor registry `capability_manager.py sync` reads) are ordinary template files with no `_exclude`/`_skip_if_exists` rule in `copier.yml` -- they are rendered into every project regardless of profile or capability selection. `sync()` with an empty `enabled` list is already covered by the existing `test_opt_out_materializes_no_provider_surface` test and is a documented no-op.

## Explicitly out of scope

- Manually merging or one-off-patching `lehard/Jara_Fin`'s own file: the fix lands in the canonical template so the next `copier update` there resolves cleanly instead of needing another manual `.rej` review.
- Preserving `lehard/Jara_Fin`'s pinned `openspec@1.8.0` as intentional customization: it is stale platform content unrelated to this specific conflict region; a normal Copier update already replaces it with the template's current `1.13.0` pin.
- `lehard/planner-agent-lab`'s anomalously-committed derived skill directories: out of scope for this fix (a separate, lower-priority drift a future change could clean up by having that project's own maintainers/rollout remove them), and not something this fix needs to touch since `sync()`/`audit()` correctly tolerate already-present, correctly-rendered surfaces.

## Tests

- `tests/test_capability_manager.py::test_audit_fails_on_a_fresh_checkout_but_passes_after_sync`: reproduces the exact failure (`audit()` returns `status: error` with the "stale or missing" issue before any `sync()`) and its resolution (`status: ok` after `sync()`), using the file's existing isolated fixture (real `capability_manager` module, tempdir project, real canonical descriptors).
- `tests/test_template_contract.py::test_generated_ci_materializes_capability_surfaces_before_platform_doctor`: asserts the generated workflow's `capability_manager.py sync` call appears before its `platform_doctor.py` call (string-position ordering, matching this file's own established style).
- `tests/test_template_contract.py::test_derived_capability_surfaces_stay_ignored_after_materialization`: asserts `.gitignore.jinja` still declares both provider ignore patterns, so materializing them in CI never risks accidentally committing them.
