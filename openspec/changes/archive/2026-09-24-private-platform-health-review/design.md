## Context

The current public workflow calls process and architecture gh-aw jobs and writes a combined public Issue. The process prompt refers to private Backlog issues while its GitHub tool guard allows public repositories only. The Backlog is private and has no Actions workflow or secrets configured today.

## Decision

The combined trigger and AI jobs execute in the private caller repository. That repository is the only full-report destination. The public repository provides reusable review workflows and helper scripts pinned by the private caller to an exact commit SHA; the private repository owns its small caller/configuration surface. The reusable gh-aw locks inline their prompt content at compile time, because activation runs in the caller checkout, where the platform source Markdown is absent. The private run reads `lehard/dev-platform` and the private caller repository only. The App token is minted during the run, limited to those repositories and to Contents/Issues/Pull requests read permissions actually exercised by the process and architecture reviews. Report creation uses the private repository's `GITHUB_TOKEN` with Issues write; the agent has read-only tools and bounded safe output.

The public combined trigger and combined Issue publisher are disabled when the private run is active. Public repository surfaces must not receive private task bodies, titles, numbers, generated summaries, or private report URLs. Public review prompts cannot be dispatched separately to create a second complete report.

The private workflow checks credential presence and access before the AI jobs. If App credentials or installation scope are missing, it creates or updates a private, explicitly `degraded` report from deterministic safe metadata, with no private evidence claims. If an AI job fails, its section states unavailable. A complete status requires successful private evidence preflight and both bounded review jobs. The report remains advisory and replaces its prior same-prefix report.

## Dependencies and rollout

GitHub App installation must include the private Backlog and have Issues read. The private repository needs `DEV_PLATFORM_APP_CLIENT_ID`, `DEV_PLATFORM_APP_PRIVATE_KEY`, and `OPENAI_API_KEY` as Actions variable/secret names. Values cannot be copied from the public repository through GitHub APIs. Downstream calls to reusable platform code use an immutable commit SHA, never `main`. Validate missing-credential degraded mode first, then full live run after credentials are configured. No private task content is committed to either repository.
