# Design: Safe migration-aware rollout repair

## Guarded recopy boundary

The rollout continues to snapshot protected project-owned paths before Copier mutation and compare them afterward. The task-intake reconciler is a known platform migration, not arbitrary project mutation. Its effect must be ordered outside the protected comparison or normalized as exactly the single marked reference it owns. The implementation SHALL use one deterministic strategy and preserve the guard for all remaining bytes/paths.

The migration is idempotent: a second run neither duplicates the reference nor broadens the allowed delta. A project-owned root `AGENTS.md` remains authoritative apart from that marked platform-owned insertion.

## Permission environment classification

Shared-workspace repair/audit remains strict on a real local collaborative workspace. The doctor detects a GitHub-hosted Actions environment before requiring group membership or setgid directory state that cannot be represented there. The CI classification is narrow and reported as advisory evidence; it must not hide ordinary permission failures on a local shared filesystem.

## Verification

Regression tests use a Cuby-like protected agent file, a Jara-like project-owned agent file, an unexpected protected mutation, and CI/local permission fixtures. The release and rollout follow existing immutable-tag and reviewed-PR lifecycle rather than adding a new dispatcher.
