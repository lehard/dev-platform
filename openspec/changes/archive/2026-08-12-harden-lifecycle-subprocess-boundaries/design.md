## Context

The current check runner executes selected shell commands as direct child processes and therefore inherits the parent environment. This is normally convenient, but repository-scoped Git variables are special: variables such as worktree/index/object-store overrides can redefine which repository a nested `git` command operates on. Test suites that intentionally create temporary repositories must not inherit that hidden binding.

Separately, the common Git helper captures stdout/stderr but relies on `subprocess` checked execution to throw. Several lifecycle entrypoints then report only the resulting exception string/traceback, hiding the diagnostic Git already supplied.

## Decisions

### Sanitize only repository-scoped Git context for validation

Do not construct a minimal clean-room environment. Start from the normal child environment and remove only Git variables whose semantics bind commands to a parent repository/worktree/index/object store, unless a specific operation explicitly opts into them. Implementation preflight should confirm the precise supported set using Git documentation/current runtime behavior and regression fixtures.

The bounded denylist is `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`,
`GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, and
`GIT_ALTERNATE_OBJECT_DIRECTORIES`. It deliberately preserves ordinary tool
context and non-binding Git configuration/identity variables. A caller that
needs a repository override can pass an environment only to that exact Git
operation; the check runner never reuses it for validation commands.

### Keep Git overrides operation-local

Where the platform itself needs a Git environment workaround, pass it explicitly to that Git subprocess/helper call. Do not mutate broad process environment state that later test/check commands inherit.

### Format checked Git failures at the common boundary

Provide one bounded, secret-safe platform error representation for checked Git failures. Callers using `check=False` keep their current result-based behavior. Higher-level lifecycle code may wrap the common error into an existing resumable state rather than losing domain semantics.

Compatibility fallback paths that previously caught `CalledProcessError` are
migrated to catch the common error where a failed Git probe is intentionally
non-terminal (for example, detecting whether a temporary directory is itself
a checkout).

### Avoid a general subprocess abstraction

The two bugs do not justify routing every shell command through a new execution framework. Make the smallest reusable changes needed in validation environment construction and Git error handling.

## Risks / Trade-offs

- Removing too many Git-related variables could break legitimate tooling. Tests must distinguish repository-binding variables from harmless Git configuration variables.
- Error formatting must not echo token-bearing URLs or secrets from stderr/command arguments; sanitization should reuse existing safe patterns where available.
- Some callers may currently depend on `CalledProcessError` specifically. Preflight must audit checked `run_git` call sites and preserve intended catch/recovery behavior or migrate them deliberately.
