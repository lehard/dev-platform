## Why
BR-576 needs a platform-launched Claude writer that physically cannot touch the integration checkout, its refs and remote, GitHub or operator credentials. The 2026-10-10 spike proved that `lifecycle_workers.run_llm` with `srt` prepended works, but only with a hand-written profile, a hand-injected token and three workarounds. This change makes that launch a reusable, tested harness primitive so the routing change can use it.

## What Changes
- Add a sandboxed writer launch primitive to the lifecycle harness that wraps an LLM command in `srt --settings <generated profile>`.
- Generate the sandbox profile in code from the writer's own paths and the protected paths: allowWrite only the disposable checkout, scratch HOME and writer tmp; denyWrite the integration checkout, its shared gitdir and every registered worktree, the push remote path when local, `~/.claude`, `~/.claude.json`, `~/.config` and the platform root; denyRead `~/.ssh`, `~/.config/gh`, `~/.gitconfig`, `~/.git-credentials`, `~/.netrc`, `~/.aws`, `~/.gnupg`, `~/Library/Keychains`, `~/.claude`, `~/.claude.json`, `~/.config/dev-platform`, `~/.npmrc`, `~/.docker` and the integration checkout; network allowlist only Anthropic hosts. `allowAppleEvents` and `enableWeakerNetworkIsolation` are never set and never read from repository files.
- Read `CLAUDE_CODE_OAUTH_TOKEN` only from the operator `[independent_review.login.claude] token_file`; fail when the setting, file or value is missing or empty, or the file mode is wider than `0600`. Remove any ambient value, put the token only in the writer environment, never in harness-git or push environments, argv, logs or results.
- Handle spike constraints: run `srt` with a short `TMPDIR` and give the writer the harness writer tmp through an inner `env TMPDIR=...`; pass the writer argv through `bash -c` with `shlex.join`; set `CLAUDE_CODE_TMPDIR` to the writer tmp.
- Refuse to launch on a non-macOS platform or when `srt`/`claude` is not resolvable, with an explicit error; no fallback to an unsandboxed launch.
- Pin the sandbox-runtime version used by the launcher.

## Success Evidence
- Unit tests prove the generated profile contents, absence of Apple Events/weaker-isolation keys, token sourcing and refusal cases, token absence from harness-git and push environments and from captured argv, the TMPDIR/argv/CLAUDE_CODE_TMPDIR shape and the non-macOS refusal.
- Full test groups and OpenSpec checks pass.

## Non-goals
Calling the primitive from model routing, routing evidence, real negative probes, DEC-0003, changing default review/repair worker launches, Linux support.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `lifecycle-workers`: sandboxed writer launch primitive with scoped Claude credential.

## Impact
`template/scripts/lifecycle_workers.py` (or a new focused `template/scripts/sandboxed_writer.py` used by it), tests under `tests/`, `docs/engineering/model-routing.md` note. No downstream behavior change by default.
