# Verification — stabilize-platform-rollout-v1

This review applies the semantic `/opsx:verify` dimensions — completeness, correctness and coherence. The literal slash workflow is not invokable from this GitHub connector session, so this document records the equivalent review without claiming the command itself ran. The change is not archived here.

## Completeness

All stabilization requirements have implementation and evidence:

1. **Upgrade behavior is tested** — `tests/upgrade_smoke.py` creates a project from the previous rollout baseline, commits project-owned customizations, updates to candidate `HEAD`, and validates preservation/doctor/compile results.
2. **Update conflicts block completion** — generated `platform_doctor.py` blocks `.rej` artifacts and Git `leftover conflict marker` findings; unit tests cover clean, `.rej`, and inline-marker states.
3. **Tool versions are deliberate** — Copier minimum/tested version is `9.17.0`; CI installs exactly `9.17.0`; doctor diagnoses installed-version compatibility.
4. **Central Actions are immutable refs** — platform workflows use full commit SHAs. The initial v4/v5 pins produced Node-runtime deprecation warnings, so they were replaced before merge with current v6 full-SHA pins; `setup-node` disables unneeded automatic package-manager caching.
5. **Release lifecycle uses real SemVer tags** — `publish-version.yml` creates `v<VERSION>` and refuses to move an existing tag. The old `release-v1.0.0` branch is explicitly documented as not being a Copier release.

Release finalization is complete:

- stabilization implementation SHA used by generated reusable CI: `dab74494c9a6ad9a77d99e73bb36774a6d42350d`;
- release commit: `ba03435a0c11da928807e2487506d1d24d8cfc39`;
- Git tag `v1.0.0` resolves to the release commit;
- matching GitHub Release `v1.0.0` exists and was created by the guarded publish workflow;
- post-release Platform CI passed fresh render and real Copier upgrade smoke for all three profiles.

## Correctness

Evidence from stabilization and release CI:

- 22 unit/integration tests pass;
- all three profiles pass fresh Copier rendering and generated doctor checks;
- all three profiles pass a real `copier update` from the pre-stabilization rollout baseline to the candidate/release template;
- project-owned `docs/engineering/project-rules.md` sentinel content and an unrelated local-only project document survive the update;
- unresolved `.rej` and inline Git conflict marker guards are unit-tested;
- contract tests reject mutable `actions/*@vN` references in central workflows;
- exact Copier `9.17.0` installation is exercised in CI;
- release publication workflow completed successfully and produced the expected tag and GitHub Release.

The first upgrade-smoke CI run failed because `copier update` attempted an interactive prompt without `--defaults`. That failure was fixed, then the entire matrix reran successfully. This is evidence that the new upgrade gate detects a class of failure the former fresh-render-only CI could not catch.

## Coherence

The change remains within the stated stabilization scope:

- no project registry, portal, fleet dashboard, or downstream fan-out automation was introduced;
- downstream CI remains exact-SHA pinned and downstream upgrades remain reviewed;
- no application repository is modified;
- no auto-merge path is added;
- existing workflow profiles and zero-hand-off lifecycle are hardened rather than expanded.

The platform now has a real `v1.0.0` Copier release boundary. The next priority is controlled adoption and observation, not further platform feature expansion. Local `/opsx:verify` and archive may be performed later by an agent with the OpenSpec workflow available.
