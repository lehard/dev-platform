## Context
Spike evidence: `~/.config/dev-platform/spike-sandbox-writer-2026-10-10/` (machine-local) — `srt-probes.json`, `writer-claude.sh`, DEC-0003 draft. `lifecycle_workers.run_llm` already gives a credential-free env, scratch HOME, writer tmp and a process-group-contained runner.

## Decisions
- One focused module builds the srt profile and the wrapped argv; `run_llm` stays the single runner. The profile is written into the harness work directory (outside every allowWrite root) and passed by path.
- Protected paths are computed from the integration repository: `git rev-parse --git-common-dir`, `git worktree list --porcelain`, the integration root and the platform root; they are resolved with realpath so `/tmp` vs `/private/tmp` aliases cannot escape.
- Token: read from the operator config resolved through the existing operator-config helper; it is added after `credential_free_env` only to the writer env. The harness-git and push env builders already start from `os.environ`; they must explicitly drop `CLAUDE_CODE_OAUTH_TOKEN` too.
- Constraint handling: `srt` is invoked with `TMPDIR=<short dir under /private/tmp/dp-srt-<uid>>`; (superseded by the BR-576 acceptance run: srt ignores these inner assignments; the writer tmp now travels as `CLAUDE_CODE_TMPDIR` in the srt process environment, and srt derives the writer `TMPDIR` from it) the original inner command was `env TMPDIR=<writer tmp> TMP=... TEMP=... CLAUDE_CODE_TMPDIR=<writer tmp> bash -c <shlex.join(argv)>`.
- Platform gate: `sys.platform == "darwin"` only; anything else raises before launch with the message that the sandboxed writer is proven only on macOS.
- Version pin: the launcher invokes `npx --yes @anthropic-ai/sandbox-runtime@<pinned>` or a resolvable `srt` binary whose `--version` matches; a mismatch is an explicit refusal.

## Risks
`sandbox-runtime` is beta; its settings schema changed (`network.deniedDomains` required). The pinned version and a schema test guard this.
