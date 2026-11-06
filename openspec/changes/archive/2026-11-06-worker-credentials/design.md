## Decisions

- **Placement.** `operator_enabled(root)` selects the source. Enabled: `token_file` is the only source, and a missing or exposed file fails even when a token is exported. Not enabled: the ambient `CLAUDE_CODE_OAUTH_TOKEN` is the job's secret; empty or absent fails naming it. There is no second try in either case.
- **One resolver.** `worker_credentials` owns reading and validating the token file (moved from `sandboxed_writer`, same errors and 0600 rule). GitHub stays the one existing `lifecycle_workers.active_gh_token`: moving it would conflict with a sibling change to that function and adds nothing. The post-merge runner keeps its own timed `gh auth token` call, which reads the same active credential, because that script stands outside the template modules.
- **Delivery.** The worker removes the ambient value from its own environment at start and holds the resolved value in memory. `provider_readiness` and the review launcher add it only to the scratch LLM environment. Finalize and post-merge kinds need no provider value and never resolve it.
- **Which kinds resolve it.** Only a kind that starts Claude: review with a Claude provider, repair kinds. A worker that requests none of them does not read the token file.
- **Codex.** The `--llm-home-file` login stays as it is.
- **Errors.** A credential error is a `WorkerError` naming the setting or variable, never the value.

## Risks

Hosted review depends on the worker telling placements apart by `[operator]`. A structure test pins that a hosted checkout has no enabled operator section, and the hosted run stays covered by its own preflight.
