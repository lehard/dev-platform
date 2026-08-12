# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual equivalent semantic OpenSpec review of completeness, correctness, and coherence against `platform-lifecycle` and this change's own deltas (no `/opsx:verify` tool integration available in this environment), plus automated platform checks and before/after benchmarking.
Automated-Checks-Evidence: automated-checks.json

## Reviewed behavior

- **Risk-class selection** (`template/scripts/select_checks.py`): `AGENTS.md`, `docs/**`, `openspec/**` prose and `template/AGENTS.md.jinja` are no longer in `full_trigger_patterns`; they route through `[checks.docs]` / `[checks.docs-template-render]` (bounded link/anchor/render checks) instead of the full suite. `template/scripts/**`, `scripts/**`, `tests/**`, `.github/workflows/**`, `.dev-platform.toml` and `dev-platform/checks.toml` remain full triggers (control-plane), and any unmapped path still fails closed to full.
- **`instruction-behavior-change` declaration**: `--declare-behavior-change RUNTIME` only takes effect for paths matching `instruction_behavior_surface_patterns`; it executes the configured `[behavioral_evidence.<runtime>]` commands as part of the same invocation. With no runtime configured (current state), a declaration fails closed to full validation with reason `behavior-declaration-unproven` — a model's own report is never accepted as evidence. `tests/test_select_checks.py` covers both the fail-closed and (fabricated-config) success paths.
- **Test isolation**: the sequential per-module audit found no writes to shared `.claude/` machine state and no fixed non-tempfile relative paths, ports, or sockets across the suite. One real order-dependency bug was found and fixed: `tests/test_platform_bootstrap.py` only imported successfully when an earlier-run module happened to have put `template/scripts` on `sys.path`; it now inserts its own. `tests/test_module_isolation.py` proves every `tests/test_*.py` module imports standalone, in isolation, in a fresh subprocess — this is the regression guard against the same class of bug recurring.
- **Canonical test groups** (`template/scripts/run_test_groups.py`, `dev-platform/checks.toml` `[test_groups.*]`): 12 groups (8 single-heavy-module + 4 balanced fast bundles) declared with `mode = "parallel"`; the resource audit found no group requiring `mode = "serial"`, though the mechanism and a dedicated test (`test_serial_group_runs_after_parallel_groups_not_concurrently_with_them`) exist for when one is needed. `--verify-coverage` proves declared-group membership is exactly equivalent to `unittest discover`'s collection (476/476 at the point of writing, 482/482 after the selector/CI test additions) — no gap, no duplicate. `tests/test_run_test_groups.py` proves a single failing mandatory group fails the aggregate result (`test_one_mandatory_group_failure_fails_the_aggregate`), matching "Partitioned required validation fails".
- **Protected-full and CI**: `dev-platform/checks.toml`'s `full_commands` and `.github/workflows/ci.yml`'s "Unit tests" step both now invoke `python3 scripts/run_test_groups.py --all`; a failing group's exit code fails that single CI job, which is the required check, so no separate cross-job aggregate was needed. `AGENTS.md`'s "## Validation" block and its local-affected guidance were updated to the same canonical entrypoint.
- **Concurrency**: two independent worktrees running the full (pre-change) suite simultaneously completed in ~308s each with all 460 tests passing and no collision, corruption, or indefinite block — refuting the prior audit's ">8 minutes" finding under current fixtures/conditions on this machine. This change's own scratch worktrees were created and removed cleanly with no effect on the task or integration checkouts.

## Benchmarks (same machine, comparable environment)

| Run | Command | Result | Wall-clock |
|---|---|---|---|
| Before (isolated) | `python3 -m unittest discover -s tests -v` | 460 tests, OK | 372.879s |
| Before (concurrent, 2 worktrees) | same, simultaneous | 460+460 tests, OK, no collision | ~308s per run |
| After (isolated) | `python3 scripts/run_test_groups.py --all` | 489 tests (final, after rebasing onto the merged `optimize-agent-context-map` change — see below), all 12 groups success | 60.53s (best isolated run), 71.73s (final rebased run), 107–152s (contended with other local load) |

Mandatory coverage is unchanged end-to-end other than the new regression tests this change itself adds (`test_module_isolation`, `test_docs_semantic_checks`, `test_run_test_groups`, plus new cases in `test_select_checks`) and `test_root_guidance_contract` (489 tests) picked up from the rebase below; no existing test was removed or weakened. Wall-clock for a genuine full run dropped roughly 3.5x–6x depending on concurrent machine load; CPU contention (documented in design.md §5) explains the run-to-run variance, not correctness.

## Real concurrency-induced flake found and fixed during archival

Running the full `protected-full` gate under the new 12-group parallel model surfaced one genuine flake: `test_delegated_write_guard.CodexTierTests.test_detection_only_when_repository_topology_is_unavailable` failed once (`mechanism` came back `detection-only:sandbox-flag-unsupported` instead of `detection-only:topology-unavailable`), but passed reliably (3/3) when re-run in isolation. Root cause: `delegated_write_guard._codex_help_text()` invoked the fake `codex exec --help` fixture subprocess with a hardcoded 10-second timeout; under the CPU contention of 12 concurrent groups (several themselves spawning many `git`/subprocess calls) that subprocess occasionally didn't respond within 10s, so the guard's own production code fell back to the "sandbox-flag-unsupported" detection-only mechanism before ever reaching the topology check the test exercises. This is a real, if narrow, instance of exactly the correctness-under-contention risk design.md commits to guarding against (not a shared-mutable-state collision, but a CPU-contention-induced timeout with an observable behavior change). Fixed by widening the timeout in `template/scripts/delegated_write_guard.py::_codex_help_text` from 10s to 30s (a real `--help` invocation answers in milliseconds; the timeout only guards a genuinely hung process, so this has no effect on the success path). No test assumed the old exact timeout value. Re-ran `tests.test_delegated_write_guard` standalone (35/35 OK) and the full 12-group suite again afterward with all groups green.

## Mid-implementation rebase onto a real docs-semantic exercise

While this change was in progress, Development Backlog #28 (`optimize-agent-context-map`) — the proposal's own named first consumer of the `docs-semantic` risk class — merged upstream and substantially restructured both `AGENTS.md` and `template/AGENTS.md.jinja` (headings renamed/consolidated, most detail relocated to `docs/engineering/*.md`). The platform's task-freshness gate correctly blocked `openspec_lifecycle.py archive` until the task branch was reconciled with the new `origin/main`.

Reconciling this by hand was a real (not fabricated) exercise of the new mechanism:

- `git merge --ff-only origin/main` applied cleanly to every changed file except `AGENTS.md`, which had one real content conflict between upstream's new "Where the detailed contract lives" routing table and this change's own added validation-entrypoint paragraph. Resolved by keeping the upstream table and moving this change's paragraph into `docs/engineering/agent-workflow.md`'s `## Validation` section — the file the routing table itself says owns that concern now.
- `render_agents_md_smoke.py`'s `REQUIRED_HEADINGS` list (`## Contract model`, `## OpenSpec and no silent divergence`, ...) was written against the pre-rebase template and became stale the moment the upstream restructure landed. Re-running it after the rebase correctly reported all required headings missing — exactly the "fails on a dropped required anchor" behavior this change's design commits to — before being updated to the new heading set (`## Sources of truth`, `## Task intents`, `## Always-on invariants`, `## Profile`, `## Entrypoints`, `## Where the detailed contract lives`, `## Ownership`).
- `run_test_groups.py --verify-coverage` correctly refused to run after the rebase added `tests/test_root_guidance_contract.py` (7 new tests) until that module was added to a declared group — proving the coverage-equivalence fail-closed behavior on a real, not fabricated, drift.
- After these repairs, `tests/test_root_guidance_contract.py` and `tests/test_template_contract.py` (32 tests together) pass against the merged `AGENTS.md`, and the full 489-test group run is green.

## Residual risk / known limitations

- The full Copier "Render factory profiles" CI step could not be executed end-to-end on this development machine: `platform_bootstrap.py`'s shared-workspace preflight requires setgid/group-write bits on `/tmp` that this macOS host's `/tmp` does not have, and this reproduces identically on an unmodified `main` checkout (confirmed), so it is a pre-existing local-environment limitation, not a regression from this change. The new `template/scripts/{run_test_groups,check_docs_links,render_agents_md_smoke}.py` files were confirmed to copy byte-identical into a freshly rendered project up to that point. CI's `ubuntu-latest` runner remains the authoritative environment for that step and was not modified by this change.
- No runtime/provider currently has a configured `[behavioral_evidence.<runtime>]` table, so `instruction-behavior-change` is exercised today only through fabricated-config unit tests, not a real declared change; it fails closed to full validation until a real targeted smoke command is configured for a runtime, which is the intended conservative default (see design.md non-goals).
- Group wall-clock is sensitive to concurrent CPU load on the machine (observed 60s–152s across runs at `jobs=7` on an 8-core host); this is expected and documented, not a hidden regression, and the required aggregate result is unaffected by it.

## Post-archive CI fix

The published PR's `validate` job failed on GitHub Actions (`ubuntu-latest`) with `ModuleNotFoundError: No module named 'jinja2'` from `test_docs_semantic_checks` and, transitively, `test_module_isolation` (which standalone-imports every test module, including that one). `jinja2` was present locally only as a side effect of this machine already having `copier` installed; the CI workflow's own "Install tested Copier" step (which would have supplied it transitively) runs *after* "Unit tests", and nothing installed `jinja2` before that point. Fixed by adding an explicit `Install Jinja2 for docs-semantic checks` step (`python3 -m pip install jinja2`) to `.github/workflows/ci.yml` immediately before "Unit tests". Local `python3 -m compileall` and YAML-parse checks passed; the corrected workflow was pushed to the same PR for CI to re-validate.

## Automated checks

- Automated-Checks-Evidence: automated-checks.json
- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 scripts/run_test_groups.py --all` — 489 tests across 12 groups, all success, coverage-equivalence proven (489/489, 0 missing, 0 duplicated), 71.73s wall-clock on the final rebased head
- `python3 template/scripts/openspec_lifecycle.py check` — OK (after this file and archival)
- `openspec validate --all --strict --no-interactive` — 16 passed, 0 failed (all current specs plus both active changes)
- `python3 scripts/check_docs_links.py` — no problems found
- `python3 scripts/render_agents_md_smoke.py` — 3 profiles OK
- `python3 -m unittest -v tests.test_module_isolation tests.test_docs_semantic_checks tests.test_run_test_groups tests.test_select_checks tests.test_root_guidance_contract tests.test_template_contract` — 69 tests, OK
