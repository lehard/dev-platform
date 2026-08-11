# GitHub Agentic Workflows pilot

`dev-platform` runs a deliberately small cloud-only pilot with GitHub Agentic
Workflows (`gh-aw`) and Codex. It is additive: deterministic CI, OpenSpec,
publication, release, and managed rollout do not depend on it.

## Version and secret contract

The exact compiler/runtime pin is stored in
`.github/aw/gh-aw-version.txt` and is currently `v0.85.4`. Install that exact
extension before changing workflow sources:

```bash
gh extension install github/gh-aw --pin "$(tr -d '[:space:]' < .github/aw/gh-aw-version.txt)" --force
gh aw doctor --repo lehard/dev-platform
```

The repository-level `.github/workflows/aw.json` maps the compiler's default
MCP gateway runtime to its immutable `v0.4.9` digest. This supported compiled
lock substitution corrects public-repository secrecy classification while
retaining `allowed-repos: public`. Do not enable `private-to-public-flows`; this
pilot must never read private repository data for a public GitHub safe output.

The only required repository Actions secret is `OPENAI_API_KEY`. It is consumed
by the Codex runtime and must never be committed, printed, copied into workflow
prompts, or included in validation evidence. Repository administrators configure
it in GitHub Actions secrets; contributors only verify the secret name exists.

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
