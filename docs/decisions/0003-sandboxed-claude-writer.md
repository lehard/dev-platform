# DEC-0003: Sandboxed Claude writer

- **Status:** Current
- **Scope:** Delegated Claude writers; macOS only
- **Decision date:** 2026-10-20
- **Authored against revision:** `896e8b816d0c0b0d8d3967a6114a3d64b3de2302`
- **Supersedes:** None
- **Superseded by:** None

## Accepted current decision

Delegated Claude writers may run as a platform-launched headless `claude -p` under sandbox-runtime
(`srt`, pinned 0.0.79) in a disposable copy of the task worktree. The route is
`scripts/model_routing.py dispatch-claude-sandboxed` (BR-576/T2), built on the launch primitive
`template/scripts/sandboxed_writer.py` (BR-576/T1). The launch is platform-observed
(`launch_evidence: platform-observed`, executed participant). The result returns as a harness-validated
patch that is applied only to unchanged task content.

HARD containment is claimed only on macOS. Linux/bubblewrap and GitHub-hosted runners are unproven and
refused. The native Agent-tool hand-off stays the default route and the detection-only checks stay in
place; switching the default and deleting detection-only code is a later Requirement.

### Token boundary

`CLAUDE_CODE_OAUTH_TOKEN` comes only from the operator `[independent_review.login.claude] token_file`
(mode 0600). It is injected only into the writer process environment and is never in harness-git or push
environments, argv, logs or routing evidence. The token file path is read- and write-denied in the profile.
The value is necessarily known to the writer process itself; the network allowlist (Anthropic hosts only)
limits where it can go. The token is also present in the trusted outer `npx`/srt launcher environment
(accepted residual risk from the BR-576/T1 review).

### Profile

- allowWrite: only the disposable checkout, the scratch home and the writer tmp.
- denyWrite: the integration checkout, its common git dir, every registered worktree, local remotes,
  `~/.claude`, `~/.claude.json`, `~/.config`, `~/.ssh`, the token file and the platform root.
- denyRead: credential stores (`~/.ssh`, `~/.config/gh`, git credentials, `~/.netrc`, `~/.aws`, `~/.gnupg`,
  `~/Library/Keychains`, `~/.claude`, `~/.config/dev-platform`, `~/Library/Application Support`, `~/.npmrc`,
  `~/.docker`), the protected paths and the platform root.
- Home-relative entries are resolved against the operator's real home, because srt runs with the scratch HOME.
- `allowAppleEvents` and `enableWeakerNetworkIsolation` are never set and never read from repository files.

## Rejected and deferred alternatives

- Keeping only the native Agent-tool hand-off is rejected: it has no OS boundary, its launch is
  self-reported, and it yields false containment violations when sibling sessions advance main.
- Claude Code `isolation: worktree` is rejected: it forks from main and cannot see uncommitted managed state.
- Keychain login inside the sandbox is rejected: the keychain is unreachable by design.
- Linux/bubblewrap and CI runners are deferred until proven.
- Merge authority on `main` is a separate boundary decided in BR-575 (CI-only merge) and is not part of this
  record.

## Evidence

Spike of 2026-10-10 (macOS, sandbox-runtime 0.0.79, Claude Code 2.1.288):

- 21 negative probes were blocked at the OS level: writes into the integration checkout and linked worktree,
  update-ref/symbolic-ref through the shared gitdir, push to integration and to a bare remote,
  `.git/hooks`/`.git/config`, `~/.claude`, reading `~/.ssh` and `~/.config/gh`, keychain via securityd,
  ssh-agent, GitHub over HTTPS, Apple Events.
- A real `claude -p` writer added code and a test, ran pytest and committed in the disposable clone while all
  six forbidden actions were refused.
- Without the sandbox every probe succeeded, including the keychain credential helper returning the owner's
  GitHub token.
- Three runtime constraints were found and handled in the harness: srt needs a short TMPDIR for its unix
  socket, and the writer gets the harness tmp as `CLAUDE_CODE_TMPDIR` in the srt process environment (srt derives the writer `TMPDIR` from it; assignments inside the sandboxed command are ignored, which the BR-576 acceptance probes caught); srt re-joins argv into one shell
  string (the writer argv passes through `bash -c` with `shlex.join`); Claude Code needs
  `CLAUDE_CODE_TMPDIR` inside the writer tmp.
- Authentication: the keychain OAuth login is unavailable under the sandbox; the supported path is
  `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`.
- Independent review of BR-576/T1 found two material gaps (home-relative denies expanding against the scratch
  HOME; token file not denied), repaired before merge.

Acceptance (BR-576, 2026-10-20, macOS, sandbox-runtime 0.0.79): this record was written by a sandboxed Claude
writer launched through `dispatch-claude-sandboxed` (platform-observed launch, executed participant, patch
applied to the task worktree). `python3 scripts/sandboxed_writer_probes.py` then ran a real sandboxed writer
against a synthetic integration repository, linked worktree and bare remote: all nine probes were refused
(write into the integration checkout and the linked worktree, `update-ref` through the shared gitdir, push to
the remote, GitHub API through the proxy, reading `~/.ssh`, `~/.config/gh` and the token file, keychain
search list) and the integration tree, worktree tree, refs and remote refs were unchanged; the token never
appeared in writer output. The first probe runs exposed that the writer's shell tool had no writable
temporary directory (constraint above), so the T3 writer itself had worked without a shell; fixed before the
recorded run.

## Code removable once the new path is the default

Input for a later deletion Requirement; nothing is removed now.

| File | Removable for the delegated Claude path | Approx. size |
| --- | --- | --- |
| `template/scripts/model_routing.py` | `_recover_claude_external_advance`, `recover_external_advance`, the Claude branches of `_postcheck`, `integration_advance` acceptance in `approve-supervisor-diff` | ~370 of ~3800 lines |
| `template/scripts/delegation_containment.py` | `verify_historical_external_advance`, `record_integration_advance`, `read_integration_advances`, `integration_advance_log`, detection-only `check_containment` branches | ~300 of ~700 lines |
| `template/scripts/delegated_write_guard.py` | the DETECTION_ONLY tier, the `write_claude_guard` PreToolUse hook path, `_classify_containment` for Claude | ~120 of ~1200 lines |
| `tests/test_model_routing.py`, `tests/test_delegation_containment.py`, `tests/test_delegated_write_guard.py` | the corresponding cases | n/a |

The native Agent-tool hand-off and its self-reported launch claim are also removable. The
supervisor-retained path (an interactive session in the integration root) is unchanged and keeps the
detection-only postcheck as its only evidence.

## Revisit triggers

- Claude Code ships a platform-verifiable launch receipt or a native read/write boundary for subagents.
- sandbox-runtime leaves beta or changes its settings schema or boundary model.
- Linux/bubblewrap support is proven.
- A probe run reports any succeeded probe.
