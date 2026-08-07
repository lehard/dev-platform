# Verification — stabilize-platform-rollout-v1

This review applies the semantic `/opsx:verify` dimensions — completeness, correctness and coherence. The literal slash workflow is not invokable from this GitHub connector session, so this document records the equivalent review without claiming the command itself ran. The change is not archived here.

## Completeness

All stabilization requirements have implementation and evidence:

1. **Upgrade behavior is tested** — `tests/upgrade_smoke.py` creates a project from the previous rollout baseline, commits project-owned customizations, updates to candidate `HEAD`, and validates preservation/doctor/compile results.
2. **Update conflicts block completion** — generated `platform_doctor.py` blocks `.rej` artifacts and Git `leftover conflict marker` findings; unit tests cover clean, `.rej`, and inline-marker states.
3. **Tool versions are deliberate** — Copier minimum/tested version is `9.17.0`; CI installs exactly `9.17.0`; doctor diagnoses installed-version compatibility.
4. **Central Actions are immutable refs** — platform workflows use full commit SHAs. The initial v4/v5 pins produced Node-runtime deprecation warnings, so they were replaced before merge with current v6 full-SHA pins; `setup-node` disables unneeded automatic package-manager caching.
5. **Release lifecycle uses real SemVer tags** — `publish-version.yml` is dormant until an explicit `VERSION` change, then creates `v<VERSION>` and refuses to move an existing tag. The old `release-v1.0.0` branch is explicitly documented as not being a Copier release.

The two intentionally post-merge items remain open: pinning generated reusable CI to the stabilization merge SHA and adding `VERSION=1.0.0` so the release commit can create the real `v1.0.0` tag/release.

## Correctness

Evidence from PR #4:

- 22 unit/integration tests pass;
- all three profiles pass fresh Copier rendering and generated doctor checks;
- all three profiles pass a real `copier update` from the pre-stabilization rollout baseline to the candidate template;
- project-owned `docs/engineering/project-rules.md` sentinel content and an unrelated local-only project document survive the update;
- unresolved `.rej` and inline Git conflict marker guards are unit-tested;
- contract tests reject mutable `actions/*@vN` references in central workflows;
- exact Copier `9.17.0` installation is exercised in CI.

The first upgrade-smoke CI run failed because `copier update` attempted an interactive prompt without `--defaults`. That failure was fixed, then the entire matrix reran successfully. This is evidence that the new upgrade gate detects a class of failure the former fresh-render-only CI could not catch.

## Coherence

The change remains within the stated stabilization scope:

- no project registry, portal, fleet dashboard, or downstream fan-out automation was introduced;
- downstream CI remains exact-SHA pinned and downstream upgrades remain reviewed;
- no application repository is modified;
- no auto-merge path is added;
- existing workflow profiles and zero-hand-off lifecycle are hardened rather than expanded.

The resulting platform is ready for a small release-finalization commit after this stabilization PR merges, then real project adoption should take precedence over further platform feature work.
