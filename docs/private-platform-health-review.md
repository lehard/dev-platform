# Private Platform Health Review

The combined Platform Health Review runs only in the private Backlog
repository. Its Actions logs, artifacts, review
issues, and notifications are private. The caller lives at
`.github/workflows/platform-health-review.yml` in that repository and pins
the reusable reviews and helpers to one immutable `dev-platform` commit.
`lehard/dev-platform` does not schedule or publish a combined report.

## Private-repository setup

Install the Dev Platform GitHub App on the private caller repository as well as
`lehard/dev-platform`. The App must have at least **Contents: read**,
**Issues: read**, and **Pull requests: read** on these repositories. In the
private repository configure:

- Actions variable `DEV_PLATFORM_APP_CLIENT_ID` (the App client ID);
- Actions secret `DEV_PLATFORM_APP_PRIVATE_KEY` (the complete App private key);
- Actions secret `OPENAI_API_KEY`.

The private caller creates an App token restricted to those two repositories
and those three read scopes, even if the App itself has other permissions for
unrelated platform operations. Its own `GITHUB_TOKEN`, with `issues: write`, is
used only to publish the private combined report. Never use a PAT, transfer a
public-repository secret, or write private Backlog titles, bodies, numbers,
summaries, or report URLs to a public repository.

## Execution

The private workflow checks out a pinned `dev-platform` commit into
`platform/`; it never references `main` for reusable workflow code. Before
either AI review, it mints the bounded App token with the pinned
`actions/create-github-app-token` action and runs:

```yaml
- name: Preflight bounded private evidence
  id: preflight
  env:
    PLATFORM_HEALTH_READ_TOKEN: ${{ steps.read-token.outputs.token }}
  run: python3 platform/scripts/private_platform_health_preflight.py
```

If the App credentials are absent, token minting fails, or this preflight
returns `private_evidence_status=degraded`, do not run either AI review. Use
the private repository token to invoke
`platform/scripts/publish_platform_health_review_report.py` with
`--private-evidence-status degraded` and the preflight's
`--unavailable-evidence` value. A degraded report is still private, contains
no secret, and cannot claim a complete audit.

Only after a successful preflight may the two independently runnable,
read-only review jobs start. Always publish one combined private report after
both jobs with `if: always()`; a failed review produces an unavailable section.
Optional notifications are allowed only from the private workflow and contain
only a short summary plus the private report link.

Validate missing-credential degraded mode before the full private run. Inspect
the private Issue and Actions run as well as the public repository for leaks.
