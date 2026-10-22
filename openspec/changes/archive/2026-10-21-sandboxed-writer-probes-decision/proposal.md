## Why
BR-576 acceptance requires reproducible negative probes under the real executor and a durable decision record. The spike probes were machine-local shell scripts with hand-edited paths; the draft DEC-0003 lives outside the repository.

## What Changes
- Add `scripts/sandboxed_writer_probes.py`: builds a synthetic integration repository with a linked worktree and a bare remote in a temporary directory, launches a real sandboxed Claude writer through the platform launch, asks it to attempt: write into the integration checkout, move its refs through the shared gitdir, push to the remote, call the GitHub API, read `~/.ssh`, `~/.config/gh` and the keychain; then verifies on the harness side that integration content and refs and the remote are unchanged. It prints a JSON report, never the token, and exits non-zero when any probe succeeded or any harness-side check changed.
- Add `docs/decisions/0003-sandboxed-claude-writer.md` (DEC-0003) with the spike and BR-576 results, the macOS-only HARD scope, the token trust boundary, the removable-code table (from the draft) as input for a later deletion Requirement, revisit triggers; CI-only merge authority referenced as BR-575's separate boundary. Update the registry index.
- Execute this change through the sandboxed Claude dispatch and record the probe report in verification.
- Fix what the acceptance run exposed in the launch primitive: srt ignores `TMPDIR`/`CLAUDE_CODE_TMPDIR` assigned inside the sandboxed command, so the writer's shell tool had no writable temporary directory. The writer tmp now travels as `CLAUDE_CODE_TMPDIR` in the srt process environment; the `sandboxed-writer-launch` delta, proposal and design are corrected to match.

## Success Evidence
- A real probe run report with every probe refused and harness checks unchanged, attached to verification.
- The routing record of this change shows a platform-observed sandboxed Claude execution with an executed participant.
- Full test groups and OpenSpec checks pass.

## Non-goals
Removing detection-only code, switching the default route, Linux, ruleset changes.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `platform-delegation`: reproducible sandbox containment probes.

## Impact
`scripts/sandboxed_writer_probes.py`, a small unit test of its report evaluation, `docs/decisions/`, `template/scripts/sandboxed_writer.py` (writer tmp fix) with its tests and the platform manifest, `docs/engineering/model-routing.md`, and the corrected `sandboxed-writer-launch` package text.
