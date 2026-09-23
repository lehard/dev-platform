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
v0.88.8 compiler's runtime. The generated GitHub tool guard retains
`allowed-repos: public`. Do not enable `private-to-public-flows`; this pilot
must never read private repository data for a public GitHub safe output.

The three pilot sources declare only the three compiler-owned mount roots
required by the `v0.88.8` safe-output backend: the workflow workspace, its
`$RUNNER_TEMP/gh-aw/safeoutputs` runtime directory, and `/tmp/gh-aw`. This is
not an agent write grant: Codex remains read-only and can request GitHub writes
only through the configured safe-output handler. Do not add broader roots,
private repository access, or `private-to-public-flows` as a workaround.

The only required repository Actions secret is `OPENAI_API_KEY`. It is consumed
by the Codex runtime and must never be committed, printed, copied into workflow
prompts, or included in validation evidence. Repository administrators configure
it in GitHub Actions secrets; contributors only verify the secret name exists.

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
- `weekly-process-backlog-review`: runs weekly on a fuzzy schedule and manually.
  It reads at most 20 open `process` issues and creates at most one bounded
  `[process-backlog]` report. It never changes source backlog issues.

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
gh aw run weekly-process-backlog-review --ref main
gh aw logs process-issue-triage --repo lehard/dev-platform
gh aw audit RUN_URL_OR_ID --repo lehard/dev-platform
```

Keep the emitted run URL, conclusion, elapsed time, reported AI credits and any
safe-output result in the active OpenSpec verification evidence. Do not raise
the configured caps without that observed evidence.
