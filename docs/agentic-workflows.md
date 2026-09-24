# GitHub Agentic Workflows pilot

`dev-platform` runs a deliberately small cloud-only pilot with GitHub Agentic
Workflows (`gh-aw`) and Codex. It is additive: deterministic CI, OpenSpec,
publication, release, and managed rollout do not depend on it.

## Version and secret contract

The exact compiler/runtime pin is stored in
`.github/aw/gh-aw-version.txt` and is currently `v0.88.8`. Install that exact
extension before changing workflow sources:

```bash
gh extension install github/gh-aw --pin "$(tr -d '[:space:]' < .github/aw/gh-aw-version.txt)" --force
gh aw doctor --repo lehard/dev-platform
```

The validator compiles the release with its resolved immutable source commit,
so generated setup-action references remain SHA-pinned.

The generated locks use the compiler's `gh-aw-mcpg` v0.4.18 image pinned by
digest. The repository-level `.github/workflows/aw.json` retains the older
v0.4.8-to-v0.4.9 substitution for legacy compilation; it does not replace the
v0.88.8 compiler's runtime. The private health review's generated GitHub
tool guard permits only `lehard/dev-platform` and
`lehard/development-backlog`. Its safe outputs run in the private caller.
Do not enable `private-to-public-flows`.

The pinned compiler calculates the MCP gateway mount allowlist from its
workspace and safe-output mounts. Do not override
`MCP_GATEWAY_ALLOWED_MOUNT_ROOTS` in `sandbox.mcp.env`: the gateway receives
literal `${GITHUB_WORKSPACE}` text there, so it rejects the real workspace
path and the safe-output backend cannot start. This allowlist is not an agent
write grant: Codex remains read-only and can request GitHub writes only
through the configured safe-output handler. Do not add broader roots or
`private-to-public-flows` as a workaround.

The public pilot requires `OPENAI_API_KEY`. The private health review also
requires a separate `OPENAI_API_KEY` secret and GitHub App configuration in
`lehard/development-backlog`; see [private-platform-health-review.md](private-platform-health-review.md).
Secret values must never be committed, printed, copied into workflow prompts,
or included in validation evidence.

## Cloud maintenance setup preflight

Before relying on an enabled cloud workflow, an operator can check its setup:

```bash
python3 scripts/cloud_maintenance_preflight.py --repo lehard/dev-platform --ref main
```

The command reads only the state of the three cloud-maintenance workflows and
the names of repository Actions secrets. If every cloud workflow is disabled,
it reports that state and exits successfully without treating it as a failure of
deterministic CI, release, or rollout. If any are enabled and `OPENAI_API_KEY`
is absent, it identifies that secret name and directs an administrator to
configure it; it does not start an agentic workflow run.

When the secret metadata is present, the command dispatches the manual-only
`Cloud Maintenance Preflight` Actions workflow. That workflow sends one
time-bounded authenticated request to the OpenAI API, discards the response
body, and emits only one of these fixed outcome categories:

- `OPENAI_PROVIDER_AUTHENTICATION_OK`
- `OPENAI_PROVIDER_INVALID_CREDENTIAL`
- `OPENAI_PROVIDER_UNREACHABLE`
- `OPENAI_PROVIDER_REJECTED`

Inspect the dispatched run in GitHub Actions for the category. Neither the
command nor the workflow prints or retrieves a secret value or provider response
body.

## Installed workflows

- `process-issue-triage`: runs after a maintainer adds the `process` label, or
  manually for a labelled issue number. Its agent has read-only GitHub access;
  safe outputs permit at most two allow-listed labels and one concise comment on
  the selected issue.
- `weekly-process-backlog-review`: is called by the private combined workflow.
  It reads a bounded set of private Backlog issues and public platform evidence,
  then creates at most one private `[process-backlog]` report. It never changes
  source backlog issues.

Both use `engine: codex`, explicit timeouts, small per-run AI-credit budgets,
and separately capped threat detection. Neither grants code-write, PR-create,
approve, merge, or autonomous remediation capability.

## Validation and operations

Run deterministic source/lock validation before publishing a workflow change:

```bash
python3 scripts/validate_agentic_workflows.py
python3 -m unittest tests.test_agentic_workflows -v
```

The validator compiles with the pinned `gh-aw` and runs its strict schema/action
reference checks,
and rejects source/lock drift. The generated `.lock.yml` files and
`.github/aw` metadata are compiler-owned; do not edit them manually.

After a workflow has reached `main`, run a controlled acceptance invocation and
inspect its actual outcome:

```bash
gh aw run process-issue-triage --ref main --raw-field issue_number=ISSUE_NUMBER
gh aw logs process-issue-triage --repo lehard/dev-platform
gh aw audit RUN_URL_OR_ID --repo lehard/dev-platform
```

Keep the emitted run URL, conclusion, elapsed time, reported AI credits and any
safe-output result in the active OpenSpec verification evidence. Do not raise
the configured caps without that observed evidence.
