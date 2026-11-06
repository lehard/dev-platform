# Verification: worker-credentials

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta spec against the implementation, scenario by scenario. No opsx tool invocation.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- One placement-selected mechanism: `worker_credentials.resolve_claude_token` reads `token_file` on an enabled `[operator]` and otherwise only the job's `CLAUDE_CODE_OAUTH_TOKEN`. `tests/test_worker_credentials.py` proves both, the disabled-operator case and that the committed public contract is the hosted placement.
- Review without an export: `provider_readiness` and `execute_review` add the resolved value to the LLM environment. Proven live on this operator node: `work-next --kinds review --providers claude --dry-run` without any exported token reports claude ready, where the same command on main reports "Not logged in".
- Export does not replace a missing file: tested with a missing file and a missing setting; the error names the setting and never the value. A wrong exported token on this node is ignored: the live probe stayed ready.
- Hosted runner without the secret: empty, blank and absent values fail naming the variable.
- Kind that starts no provider: `llm_env` reads nothing without `claude`, and only review, the probe and a repair writer call it.
- Containment: the check environment drops the token, the push environment drops it, and harness git already did. The probe test proves the value is in the launcher environment and not in `os.environ`.
- Ambient removal: `work-next` removes an exported token on the operator node at start; `hosted` placement keeps it. The sandboxed writer path is unchanged and now reads through the same module.
- A `--llm-command` repair writer receives the credential through `run_llm` `extra_env`, because the ambient value is gone.

## Evidence

- `tests/test_worker_credentials.py`, `tests/test_sandboxed_writer.py`, `tests/test_lifecycle_workers.py` pass; selected checks are recorded in `automated-checks.json`.

## Not verified

- No live full review job yet: the first real one is the review of this candidate, and a hosted review is not exercised by this change.
- The post-merge runner keeps its own timed `gh auth token` call, recorded in the design.
