## Context

Several platform releases run on one machine and share one machine-local pool TOML and directory: the pool exists since v1.9.5, and releases before it run unpooled. `load_config` rejects unknown keys, so a new key would make every pooled older release fail until each project is updated, and automatic rollout is off (DEC-0005). `DEV_PLATFORM_TEST_JOBS` is honoured by every release.

## Decisions

- **Weight via `DEV_PLATFORM_TEST_JOBS`, not a new key.** The recommended run weight is the existing variable in the machine's agent environment. `status` makes a mismatch between `tokens` and the weight visible and warns; it does not reject, because older releases and other projects may legitimately run another weight.
- **macOS memory signal is the kernel pressure level.** `sysctl -n kern.memorystatus_vm_pressure_level` returns 1 (normal), 2 (warn) or 4 (critical); admission waits above 1. The swap used/total ratio is not used: macOS adds swap files on demand, so used is normally close to total and the ratio would need a new threshold. A non-integer or unknown level is an explicit error, never "assume normal".
- **Light selection by explicit labels.** The platform does not know a project's commands, so it uses the existing `evidence_types` labels: only a selection whose every command is labelled `configuration` or `syntax`, with no affected-test precheck, leases one token. An unlabelled or `test` command keeps the full weight.
- **Blocker first.** One evaluation function returns the blocker kind, value and threshold for both the waiting line and `status`, so the two never disagree.
- **Thresholds by measurement.** `max_load_per_cpu` and `min_available_memory_mb` for the owner's Mac are chosen from a measurement with two concurrent heavy runs; the values, the edits to `/Users/Shared/dev-platform-pool.toml` and `~/.bash_profile`, and the rollback are reported. Applying them and the measurement wait for the coordinator's signal, because other agents' runs use the pool.

## Compatibility

Older pooled releases on the same machine keep their weight and memory formula until updated; they share tickets and slots unchanged. Because they also honour `DEV_PLATFORM_TEST_JOBS`, setting it to 3 aligns their weight as well. This is documented, and a test proves a configuration file valid for the current schema stays valid.
