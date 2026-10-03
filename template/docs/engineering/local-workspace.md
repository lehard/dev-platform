# Operator-local workspace attachment

`template/scripts/local_workspace.py` is a self-contained, opt-in source
permission runtime. It complements `shared_workspace.py`: the existing Git and
platform-state allowlist is unchanged. No registry, machine path, user identity,
or installed runtime belongs in tracked project configuration.

An operator reviews the group, workspace roots, exact Git origin strings and
source roots before installing. Both users must be effective members of the
chosen local group; restart sessions after enrollment. The runtime never uses
sudo. The shared external runtime directory must already be accessible to that
group, with group write/traversal and directory setgid. Use a non-symlink,
absolute path outside all project checkouts. Each user must have Python 3.11+
and Git on the machine. LaunchAgents use the installing user's Python executable; shared Git hooks resolve `python3` from the invoking user's PATH.

Create an external registry with this shape, replacing the illustrative values
with reviewed machine-local values:

```json
{
  "version": 1,
  "runtime_dir": "/reviewed/local-runtime",
  "workspace_roots": ["/reviewed/workspace"],
  "projects": [
    {
      "origin": "https://example.invalid/team/project.git",
      "group": "reviewed-group",
      "source_roots": ["src", "tests"],
      "exclude": ["config/private/**"]
    }
  ]
}
```

Origins match exactly, without SSH/HTTPS alias normalization. Discovery examines
only first-level Git integration checkouts under those roots; it skips linked
checkouts, symlinks and unrelated repositories. Missing projects and permission
failures are reported, not silently treated as installed. Explicit source roots
bound both tracked and untracked files; individual root files can be named explicitly. Directory
ancestors are checked for traversal and inheritance. Git metadata, agent state,
credentials, `.env*`, keys, common dependency/build/cache directories and links
are always excluded. Explicit `.agents/skills` is permitted; other `.agents` state is excluded. Extra exclusions use repository-relative glob patterns.
Review project-specific credential and generated-file conventions before
attachment. Hardlinked files are reported without repair. There is no blanket
recursive repair of a workspace.

From a reviewed platform release or this source checkout, run:

```bash
python3 scripts/local_workspace.py sync --registry /reviewed/registry.json
python3 scripts/local_workspace.py install-agent --registry /reviewed/registry.json
```

Sync copies the runtime into the external directory, records its SHA-256, and
creates per-checkout policies and hook dispatchers there. Concurrent sync uses
a non-blocking shared lock and reports a retry when another sync is active. Repeated sync leaves
identical files unchanged. For automatic runtime upgrades, configure `runtime_source` with `checkout`,
`origin`, `branch` and repository-relative `path`. Only the committed runtime
blob on that exact reviewed branch is eligible; uncommitted runtime changes
block updates. Installed automation consumes and executes the verified update.
Without `runtime_source`, update by running sync from a reviewed release.
Generated external files are atomically updated by cooperating group members;
application source remains owner-only. Shared generated directories require
group read/write/traversal and setgid. Optional per-project `checkout_names`
limits attachment to canonical clones, excluding recovery copies.
A checkout with unresolved source findings is diagnosed before new attachment.


Each user separately installs their own macOS LaunchAgent. It runs at login and
every five minutes, with umask `0002`, writing a per-uid log in the runtime
directory. Install retries an existing but unloaded agent. Unsupported OS,
launchctl errors and missing runtime are explicit failures. Automation changes
permission metadata and local Git attachment configuration only; it never
commits, publishes, resets, stashes or edits source content.

`core.hooksPath` points to the generated dispatcher. The original setting and
resolved hooks directory are retained in an attachment receipt. Delegation reads
the original hook dynamically, preserving its arguments, stdin, stdout and
failure status. Refreshing doctor-managed hooks in that directory keeps working.
When operator hooks use a custom directory, marked doctor pre-commit and
pre-merge hooks in the normal Git directory are also invoked. Non-terminal stdin
is replayed to both hooks; the first failure is returned. After a successful
hook, an owner repair/audit runs; a remaining finding blocks
the hook. Updating the hooks configuration outside this runtime requires operator
review before reattachment or removal. Source policy is enabled by the local Git
key `devPlatform.localWorkspacePolicy`, including for linked worktrees.

In an attached checkout or current-user worktree:

```bash
python3 /reviewed/local-runtime/local_workspace.py check
python3 /reviewed/local-runtime/local_workspace.py repair
python3 /reviewed/local-runtime/local_workspace.py run -- python3 scripts/start_worktree.py task-name
```

The launcher sets umask `0002`, runs owner repair/admission before the command,
and audits again even when the command fails. The original command's failure
status is retained. Hooks and periodic audits catch restrictive or atomically
replaced files; an arbitrary editor's initial mask cannot be guaranteed in
advance. Updated lifecycle scripts independently run a read-only source
admission before mutation; older downstream scripts use the launcher until a
reviewed Copier update supplies that integration. New template renderings ship
the same runtime but stay opted out without the local Git key. Copier never
creates or replaces the external registry or hooks receipts.

Only current-user owned paths can be repaired, after group-membership and
repository-identity checks. Foreign-owner drift reports the path, uid, gid,
mode and minimal owner action. Direct execution and hooks also require the task to stay within reviewed workspace roots. A linked task must have current-user owned root,
Git marker and administration directory; otherwise launch and repair refuse.
The post-checkout hook audits the new current-user task's source and exact Git
administration directory. Periodic sync audits current-user tasks only when
Git registers them below the same reviewed workspace root. Foreign active worktrees are never taken over. The
central Mac adapter's narrowly scoped workaround remains separate; this runtime
does not waive setgid or other defects. A filesystem that strips setgid reports
an unresolved finding even after owner repair.

Remove each user's automation, then detach each integration checkout explicitly:

```bash
python3 /reviewed/local-runtime/local_workspace.py remove-agent --registry /reviewed/registry.json
python3 /reviewed/local-runtime/local_workspace.py remove --root /reviewed/workspace/project
```

A live LaunchAgent must unload successfully before its plist is removed; failures are reported with the plist retained. Removal restores the original `core.hooksPath`, unsets the policy key and removes
only verified generated dispatcher hooks/attachment receipt. Modified dispatcher
hooks cause refusal. Original hooks and unknown files remain. The external
registry, policies and runtime remain for operator review; stop every user's
LaunchAgent before disposing of that shared installation, or sync will reattach.

Acceptance on the real machine requires each account to create a restrictive
source file and an atomic replacement in registered projects, run its audit,
confirm group read/write plus directory setgid, and verify the other account's
active worktree is unchanged. Record both actual identities and outcomes in
local evidence. Simulated ownership and a generated plist test are useful
regressions but do not prove two-user execution or a loaded real LaunchAgent.
