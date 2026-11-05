## Decisions

- **Shape.** The sandbox runs `platform_version = "source"`. Rendering is not an option: the template ships no queue workflows and any other version selects portable mode. The runner composes the sandbox tree from the head under test plus a fixture overlay that replaces only CI, checks and the source contract.
- **Registry.** The sandbox is outside the production registry. The runner writes its own operator config and a one-entry registry in its working directory and selects them explicitly. Rollout cannot see it.
- **Trust.** Candidate code runs on the sandbox default branch, so the production App key never goes there. The sandbox has a dedicated App installed only on it. The runner refuses before any write when the target is not the configured sandbox.
- **Private clone.** `harness_push_env` already supplies a process-scoped credential. Clone and fetch reuse that mechanism, so no token reaches argv, URLs, checkout config, logs or a writer environment. A private repository without a token fails by name.
- **Private reads.** Live run: a green required check was invisible to a token limited to contents and pull requests. The sandbox App and its snapshot workflows add Checks read and Actions read. Production workflows and the production App stay unchanged; `token_read_permissions` makes the difference explicit.
- **Reset.** Forward only: close open PRs and Issues, delete work branches, commit the baseline tree on top of main. Queue state lives in comments of closed PRs and new numbers do not meet it. Reset runs at each run start, so a failed run is not inherited.
- **Baseline write.** The runner writes main as repository admin. Sandbox protection allows that one path, which differs from production main and is documented.
- **Lock.** A live marker in the sandbox refuses a second concurrent run.
- **Manual step.** Any action outside documented entrypoints. The runner never edits labels, lifecycle comments or queue records.
- **Failure.** A failed or timed-out step reports scenario, step and observed state, and the command exits non-zero. A known failure is listed explicitly and is never green.

## Risks

Source mode outside this repository has never run. New dead ends go to the coordinator with a reproduction rather than being worked around.
