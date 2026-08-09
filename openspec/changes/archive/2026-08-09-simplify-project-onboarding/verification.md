# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic completeness/correctness/coherence review plus Platform CI

## Evidence

- Repository classification is conservative: process markers and size thresholds force reviewed migration.
- Fresh adoption validates Copier conflicts, platform doctor, OpenSpec lifecycle hygiene, strict OpenSpec validation and selected project checks before auto-merge.
- Existing adoption never sets the safe-fresh OpenSpec bootstrap marker and stops at a reviewable PR.
- Managed promotion is explicit/idempotent and ordinary rollout still ignores candidate/excluded projects.
- OpenSpec full workflow selection is isolated through temporary `XDG_CONFIG_HOME`; persistent developer-global OpenSpec config is not modified.
- Generated OpenSpec YAML colon-bearing guidance is quoted and Codex verify detection uses `.codex/skills`.
- Unit tests cover classifier defaults, promotion/reclassification and readiness workflow selection; factory CI renders all profiles and upgrade smoke remains active.
