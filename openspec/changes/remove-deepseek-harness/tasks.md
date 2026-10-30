## 1. Removal
- [x] 1.1 Delete the DeepSeek adapter, shim, observation profile, requirements file, docs and test.
- [x] 1.2 Remove the template config section, protected-surface entries, checks.toml entry, Explorer node and doc link.
- [x] 1.3 `validate_platform_config`: explicit error for a leftover `[experimental_runtime.deepseek_harness]`; test.

## 2. Verification
- [x] 2.1 Regenerate the manifest; prove a Copier update from v3.0.0 deletes the files and a new render has none.
- [x] 2.2 Full validation and semantic OpenSpec verification.
