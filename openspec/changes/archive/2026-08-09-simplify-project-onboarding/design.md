# Design

## Principle

Human chooses the repository; Dev Platform chooses the process.

## Classification

`adopt_project.py` uses fail-safe signals. Existing Dev Platform metadata means `adopted`. Existing agent/OpenSpec/CI/process markers or repository-size thresholds mean `existing`. Only repositories without those signals qualify as `fresh`.

The detector is intentionally conservative. A false `existing` result costs only a review; a false `fresh` result could auto-merge, so ambiguous repositories take the cautious path.

## Fresh path

The central workflow authenticates with the existing least-privilege Dev Platform GitHub App, renders an exact immutable release using platform defaults, allows bootstrap to initialize OpenSpec only through an explicit safe-fresh environment marker, runs platform/OpenSpec/project checks, pushes an auditable PR, and squash-merges it only after validation. The central registry is then mechanically promoted on the latest `main`.

## Existing path

The same workflow renders into an automation branch but deliberately disables safe-fresh OpenSpec initialization and leaves the PR open. After review/merge, rerunning the same operation detects platform metadata and performs only registry promotion.

## OpenSpec integration

The platform writes a temporary XDG OpenSpec global config selecting the full/custom workflow set, runs OpenSpec, then discards that temporary config. This provides `verify` and other expanded workflows without changing a developer's persistent OpenSpec preferences. Generated Claude/Codex artifacts remain ignored machine-local files.

## Local readiness

`scripts/dev.py ready` synchronizes main only when currently on main, regenerates selected OpenSpec adapters for a fresh clone, then runs platform and agent doctors.

## Rollback and compatibility

No existing managed project changes behavior until it adopts the new platform release. Ordinary rollout remains PR-only. The new `scripts/dev.py` is platform-managed and required after v1.4.0 render/update. Existing project-owned contracts remain protected by Copier ownership rules.
