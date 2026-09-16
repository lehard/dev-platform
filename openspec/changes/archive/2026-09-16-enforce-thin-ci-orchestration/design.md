# Design: Thin CI orchestration over repository-owned entrypoints

## Decisions

1. **GitHub Actions stays the default control plane.** This change does not replace the existing GitHub-centric PR/check/release workflow.
2. **Portable capability owns an executable entrypoint.** Test, build, verification, release or deploy behavior that can reasonably run outside GitHub Actions SHOULD live behind a repository-owned command/script and be callable locally by an agent or developer.
3. **Provider-native orchestration stays provider-native.** Event triggers, permissions, concurrency, checkout/setup, secrets/environment wiring, artifacts/check/status integration and similarly GitHub-specific control-plane mechanics may remain in workflow YAML.
4. **No speculative CI abstraction.** Do not add a provider interface, runner manager, GitLab/Jenkins adapter or generic pipeline DSL merely to make future replacement theoretically easier.
5. **No purity refactor.** Existing central Platform CI shell blocks are moved only when they contain a real reusable/portable capability whose extraction improves reproducibility or reuse; line count alone is not a reason.
6. **Agent guidance is bounded.** Add one durable invariant or concern pointer to the root/rendered agent contract and keep detailed CI ownership guidance in the existing canonical CI/release documentation rather than copying policy into tool-specific files.
7. **Template behavior is the regression target.** New and updated managed projects must retain repository-owned execution entrypoints and a thin generated `dev-platform.yml`; verification should cover rendered-template coherence, not merely prose.
8. **Self-hosted remains an optimization option.** Hosted versus self-hosted runners are execution placement decisions and do not change the ownership boundary; no self-hosted machinery is added until cost, queueing or environment requirements justify it.
