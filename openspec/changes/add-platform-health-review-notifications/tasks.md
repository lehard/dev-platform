# Tasks

## 1. Specify optional notification delivery

- [x] Add the notification ADDED Requirement(s) to the `platform-health-review` OpenSpec delta: GitHub as always-present base channel, Telegram and generic webhook as optional adapters, secrets confined to GitHub Actions repository secrets, and unconfigured channels silently skipped. (Already present in `specs/platform-health-review/spec.md` as materialized from the managed Issue; reviewed and left unchanged as accurate.)

## 2. Implement the notification step

- [x] Add a repository-owned notification script (`scripts/notify_platform_health_review.py`) that formats a short summary + report-Issue link and sends it to each configured channel independently.
- [x] Wire a separate, non-agentic GitHub Actions step (after the report step) that invokes the script, passing only the secrets present in the environment. Added a `notify` job to `.github/workflows/platform-health-review.yml` (`needs: publish-report`, `if: always() && needs.publish-report.result == 'success'`), and extended `scripts/publish_platform_health_review_report.py` / the `publish-report` job's step+job outputs so the report Issue URL/number and a short summary are available to `notify` without re-deriving them.
- [x] Confirm no channel secret is read from or written to `dev-platform/capabilities.toml`, `.dev-platform.toml`, or any other portable/public project configuration file. (Verified via `grep`; secrets are referenced only via `secrets.*` in the workflow YAML and read from `os.environ` in the script.)

## 3. Verify and document

- [ ] Exercise the notification step with a test Telegram/webhook target and confirm exactly one message is sent per configured channel, with no channel configured resulting in a clean no-op. **Deliberately deferred**: this requires a real external send, which is out of scope for this round (see `verification.md`).
- [x] Run a secret-scan/public-distribution check confirming no channel secret appears in tracked source or portable config.
- [x] Run `openspec validate --strict` for the change, full platform test groups, and semantic OpenSpec verification; record truthful evidence in `verification.md`.

## Logical commits

- [x] Commit the OpenSpec delta, the notification script, and the workflow wiring together, since they jointly define one observable capability: optional external notification for the Platform Health Review report.
