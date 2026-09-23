# Design: Deterministic, secret-isolated notification delivery

## Boundary

Notification delivery is intentionally kept outside the sandboxed gh-aw agent job. The agent job's only output relevant here is the published report Issue (URL + short summary text it already produces). A separate, ordinary (non-agentic) GitHub Actions job/step then reads that output and performs delivery. This keeps the "thin CI, portable entrypoint" boundary: the actual formatting/sending logic lives in a repository-owned script invoked by workflow YAML, not embedded as agent prompt behavior and not embedded as inline shell in the workflow file.

## Secrets and configuration

- Enablement (which channels to attempt) is ordinary, portable, project-owned configuration (for example, a capability descriptor or workflow input) — safe to commit and safe to be public.
- Values (Telegram bot token/chat id, webhook URL) are GitHub Actions repository secrets only, referenced by the workflow YAML via `secrets.*`, exactly like the existing `OPENAI_API_KEY` engine credential. They are never read from `dev-platform/capabilities.toml`, `.dev-platform.toml`, or any other file in the portable project tree.
- A channel with an unset secret is treated as "not configured" and is silently skipped, not treated as an error, so GitHub remains fully sufficient as the base channel with zero external configuration.

## Execution model

1. The report step (from `add-platform-health-review-report`) publishes the report Issue and exposes its URL and a short (few-line) summary as a job output.
2. A subsequent ordinary Actions step runs a repository-owned script (e.g. `scripts/notify_platform_health_review.py`) that reads that output plus whichever secrets are present in its environment, and performs delivery to each configured channel independently (a failure sending to one channel does not block the other).
3. The script never receives write access to the repository; its only side effect is an outbound HTTP call to Telegram's API and/or the configured webhook URL.

## Verification note

`tasks.md` originally listed a live test-send smoke check in `lehard/dev-platform`
as a pre-archive verification item. As established by prerequisite changes
`add-architecture-health-cloud-review`, `add-platform-health-review-orchestration`,
and `add-platform-health-review-report`, GitHub Actions only recognizes a
`workflow_dispatch`-triggerable workflow, and every reusable workflow it
calls, once their files exist on the repository's **default branch**. This
change's `notify` job is new inside the already-merged
`platform-health-review.yml`, so the same structural constraint applies.
Separately, this repository has no `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`/
`NOTIFY_WEBHOOK_URL` secret configured yet, so even a post-merge dispatch can
only confirm the "no channel configured -> clean no-op" scenario, not a real
delivered message -- that half requires the user to provision real secrets,
which is outside this task's control (entering credentials is not something
an automated agent does). The live-dispatch confirmation is therefore an
explicit **post-merge** follow-up (see `tasks.md`): everything verifiable
pre-merge (unit tests covering every channel-configuration combination and
secret redaction with mocked HTTP calls, `openspec validate --strict`, and
the full platform test suite) was verified before archive.

## Compatibility and rollback

Disabling all channels (unsetting both the enablement config and the secrets) returns to today's GitHub-only behavior with no code path removed — the step simply has nothing configured to send. Removing the notification step/script entirely is a clean revert with no data migration.

## Risks and mitigations

- Risk: a leaked webhook URL or bot token could be used to send messages as this integration. Mitigation: secrets stay in GitHub Actions' encrypted secret store, never printed to logs, never included in the agent job's context, and rotated the same way `OPENAI_API_KEY` already is if ever exposed.
- Risk: an outbound call to an external service could hang or fail the whole run. Mitigation: the notification step is separate from and non-blocking for the report step; it runs with its own bounded timeout, and its failure does not retroactively affect the already-published report Issue.
- Risk: sending the full report body to an external chat/webhook could leak more than intended. Mitigation: the notification payload is explicitly bounded to a short summary and a link, never the full report content, per the requirement's own exclusion.
