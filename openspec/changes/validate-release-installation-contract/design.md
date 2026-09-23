# Design

The central script constructs temporary Git repositories and uses Copier against the candidate checkout. It runs fresh installation cases, then upgrades a baseline rendered from the latest stable tag to candidate HEAD. The chosen cases cover both GitHub harness modes and the supported GitLab platform harness, for both copy and update. Each result is checked through a shared, platform-only installation validation function: Copier reject detection, staged and unstaged diff hygiene, platform doctor, required rendered files, and capability surface consistency. Copier answers receive the same trailing-newline normalization as rollout before diff hygiene. The script reports a failed case with its configuration.

CI calls the entrypoint once after setup. The release publication workflow calls it before creating the immutable tag; a failure prevents tag and release creation even if a release commit bypasses PR CI. The script never invokes `select_checks.py` or downstream application commands.

Risks: a historical tag may be unavailable in a fresh-history checkout. PR CI and release jobs have full tag history; the release gate must fail closed without an upgrade baseline. Local snapshot tests may explicitly report a skip. Copier mutations stay inside disposable temporary directories.
