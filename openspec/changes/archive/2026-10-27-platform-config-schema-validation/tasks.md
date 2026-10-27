## 1. Schema

- [x] 1.1 `_platform_common.py`: the schema and `PlatformConfigError`; `read_project_config` / `read_platform_config` fail on a missing file, missing required key and wrong type, and fill only the optional schema default.
- [x] 1.2 Accessors read validated values without substitutes (`protected_main`, `pr_merge_mode` contradictions removed).

## 2. Call sites

- [x] 2.1 Replace `get(<required key>, <default>)` reads in `template/scripts` with direct reads.
- [x] 2.2 Replace them in `scripts/` where they read the platform configuration.
- [x] 2.3 Remove the duplicated path-default table in `shared_workspace.py`; route raw loaders (`dev.py`, `platform_bootstrap.py`, `shared_workspace.py`, `requirement_integration.py`) through the validated reader.

## 3. Documentation and verification

- [x] 3.1 Document required keys and the optional key with its default.
- [x] 3.2 Tests: shared complete-config fixture; missing file, missing key, wrong type, optional default; update tests that wrote partial configs.
- [x] 3.3 Run full validation and semantic OpenSpec verification.
