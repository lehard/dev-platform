OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the agent-runtime, model-routing and platform-config deltas, proposal, design and tasks; targeted unit tests; a real Copier proof (render v3.0.0, commit, `copier update` to the change head; and a fresh render of the change head) in a group-shared temporary directory; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Deleted: `template/scripts/deepseek_harness_adapter.py`, `scripts/deepseek_harness_adapter.py`, `template/dev-platform/deepseek-harness-observation.cordis.yml`, `template/requirements/deepseek-harness.txt`, both `deepseek-harness-runtime.md` docs, `tests/test_deepseek_harness_runtime.py`; the template config section, protected-surface entries, checks.toml entry, Explorer node (its published path is retired in the Explorer test list with a comment) and the upstream-substitution link.
- `validate_platform_config` fails explicitly on a leftover `[experimental_runtime.deepseek_harness]`. Because `.dev-platform.toml` is `_skip_if_exists`, `platform_bootstrap.remove_shipped_deepseek_section` (first step of the Copier task) deletes the one shipped form; any other form fails on read.
- Specs: agent-runtime removes three DeepSeek requirements and replaces three generic ones with runtime-neutral names and scenarios; model-routing drops the DeepSeek/Cordis mention; platform-config adds the leftover-section requirement.

## Completeness

- Copier proof (2026-10-30): a v3.0.0 render contains the adapter, docs, observation profile, requirements file and section; `copier update --vcs-ref <change head> --conflict rej` exits 0, leaves no `.rej`, and afterwards no `*deepseek*` file exists and `.dev-platform.toml` has no DeepSeek text. A fresh render of the change head contains none of them.
- Config: `RemovedDeepSeekConfigTests` (leftover section error naming file and fix; absent or empty `experimental_runtime` still reads), `RemovedDeepSeekSectionTests` (shipped section removed with neighbours intact, idempotent; modified section kept and rejected on read).
- No reference to DeepSeek remains in `scripts/`, `template/`, `docs/` (outside `docs/decisions/`), `tests/`, `explorer/` or `dev-platform/checks.toml`; specs change at archive.

## Not verified / limits

- The untracked operator `.dev-platform.toml` in the integration root and the copies in active worktrees still carry the shipped section (machine-local, not touched by this change); after merge they fail on read until the section is deleted. Raised to the coordinator with options before publication.
- The first Copier proof attempt in the session scratchpad failed in the bootstrap's shared-workspace preflight (no group setgid on a temporary directory); the recorded proof ran in a group-shared directory.
- Independent review: advisories only. The proposal's update-mechanism sentence was corrected to the bootstrap removal; the exact-match-only removal is intended (an edited section is never rewritten and fails on read with the fix named).
- Window run (2026-10-31): the first affected-test precheck failed once in `test_pr_review_gate.test_developer_review_repair_review_and_evidence_reuse`, with `model_routing` argparse reading the unittest runner's argv ("invalid choice: 'test_coordinator_preflight'"), only in the parallel group run. The module passes alone and in group order, and the same intermittent argv failure was seen earlier in an unrelated BR-775 run (pre-existing, `unknown` until reproduced on base). The selected checks were rerun once.
- `tests/test_shared_writer_guard.py` reviewed baseline gains `platform_bootstrap.py:remove_shipped_deepseek_section:write_text` (same kind as `sync_platform_version`).
