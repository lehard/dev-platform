## Context

The adapter is reached only through its own entrypoint and an explicit experimental opt-in; nothing else imports it. `experimental_runtime` is read only by the adapter. `_platform_common.validate_platform_config` is the single read-time schema check of `.dev-platform.toml`.

## Decisions

- **Delete, do not stub.** All DeepSeek files go; no compatibility shim remains.
- **Explicit leftover error.** `validate_platform_config` checks `config.get("experimental_runtime")` for a `deepseek_harness` table and raises `PlatformConfigError(f"{path} still has [experimental_runtime.deepseek_harness]; DeepSeek Harness was removed from Dev Platform: delete that section")`. An empty or absent `experimental_runtime` stays valid. No silent ignore.
- **Specs.** REMOVED: "DeepSeek Harness integration is pinned and isolated", "DeepSeek Harness upgrades are explicit compatibility events", "Initial DSH adapter scope remains deliberately narrow". The generic "External runtime execution preserves one lifecycle owner", "External runtime containment fails closed" and "External runtime evidence uses the common execution provenance" are REMOVED and re-ADDED under runtime-neutral names with runtime-neutral scenarios, because their scenarios are DeepSeek-specific and the validator does not allow dropping scenarios through MODIFIED. model-routing "Efficiency evidence remains runtime-neutral and historically compatible" is MODIFIED (text only). platform-config gains the leftover-section requirement.
- **Explorer.** Remove the node from `explorer/map.toml` with whatever the Explorer requires for a retired published page (as its tests define).
- **Copier proof.** Render the last release (v3.0.0) into a temporary project, commit, then `copier update` to the change head and check the files and section are gone.

## Risks

- A project that edited its rendered DeepSeek section keeps it after update and gets the explicit error; the message names the fix.
