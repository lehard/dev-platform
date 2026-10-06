## Context
Coordinator state lives in PR markers (coordinator-candidate-states). `disposable_repository_sandbox.py` gives isolated copies; delegation containment checks content changes.

## Decisions
1. Claim: a marker `{job, worker, head, expires_at}`; the earliest valid unexpired claim for the job wins (comment order); a worker re-reads after posting and aborts if it lost.
2. Worker: advertises job kinds it can run (provider CLIs and credentials available); same entrypoint locally, on a server or from an agent session.
3. Authority: the harness strips `GH_TOKEN`, `GITHUB_TOKEN`, credential helpers and SSH agents from the LLM environment, runs it in a disposable checkout, then validates the produced commits and pushes the validated fast-forward itself with an expected-head lease (`--force-with-lease=refs/heads/<branch>:<expected-head>`), so the push lands only on the exact head the job was bound to. Reviewer jobs get no write path at all.

## Risks and Mitigations
A local worker uses operator credentials for the harness push: the LLM process never sees them. A crashed worker: claims expire. Prompt injection from PR content: no credentials and harness validation bound the impact.

## Verification
Fixture repositories and fake LLM commands for claims, expiry, stale heads, environment scrubbing and push validation.
