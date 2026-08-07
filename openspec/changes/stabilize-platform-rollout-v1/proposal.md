# Proposal: stabilize-platform-rollout-v1

## Why

`dev-platform` is feature-complete enough for initial rollout, but rollout safety still has four gaps that can cause drift or silent breakage before the first real dogfood cycle:

1. Copier template lifecycle does not yet have a true SemVer tag/release path.
2. CI validates fresh renders but not upgrade behavior from an already-generated project.
3. Copier/Git conflict artifacts are not a blocking doctor condition.
4. CI dependencies and Copier itself still contain mutable/unbounded version references.

These are stabilization concerns, not new platform capabilities.

## Goals

- make the Copier update path a first-class tested contract;
- block unresolved update conflicts before work is finalized;
- pin the exact Copier version currently tested by the platform;
- pin GitHub-owned Actions used by central workflows to full commit SHAs;
- introduce a guarded SemVer tag/release mechanism without automatic downstream upgrades.

## Non-goals

- no project registry, fleet dashboard, Backstage-style portal, or new developer platform UI;
- no automatic downstream upgrade PR fan-out yet;
- no change to `Jara_Fin` or any application repository;
- no auto-merge of platform or downstream changes.

## Compatibility

New projects get the stronger doctor and explicit Copier compatibility metadata. Existing projects receive these through reviewed Copier updates. Project-owned rules and files must remain preserved during upgrade smoke testing.
