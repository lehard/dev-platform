# Public distribution cutover

The public product is cut over from a verified sanitized snapshot, not by
rewriting historical references that are merely project or operator names.
Run `python3 scripts/public_distribution.py audit` and
`python3 scripts/public_distribution.py history-audit`, render a clean default
project, and complete the GitLab sandbox proof before preparing a deterministic
tar snapshot with `snapshot --output <path>`. The current-tree audit covers
the exact product candidate set used by that snapshot. It permits only the
canonical `lehard/dev-platform` product identity; personal downstream,
backlog, fleet, and bot references must be replaced with synthetic examples,
and known project-specific compatibility markers (see
`scripts/public_distribution.py` `COMPATIBILITY_MARKERS`) are blocked even
when they are not written as `owner/repo`. The candidate set is a canonical,
self-contained source checkout, not a reduced runtime export: `tests/` and
accepted `openspec/specs/` plus current OpenSpec lifecycle configuration ship
so a fresh clone stays developable, testable, and spec-driven from its first
commit. Only maintenance-only history (`openspec/changes/archive/`), local
agent/runtime state, and the central checkout's own `.dev-platform.toml` are
deliberately excluded from the product candidate set. The shipped template
remains the portable configuration surface.

The history audit is a separate bounded reachable-blob scan for supported
GitHub, GitLab, and AWS credential signatures. Its JSON receipt records the
refs, object limit, examined object count, pattern classes, and limitations;
it never prints possible credential values. A clean result is not a universal
claim that no secret ever existed. Rerun both audits and the snapshot if the
source revision changes after evidence is recorded.

If the audit identifies an actual credential or sensitive payload, treat it as
a security incident: rotate or revoke it first, record that remediation, then
decide whether targeted history cleanup is necessary. Removing a Git reference
does not invalidate an already exposed credential.

Owner/admin gate:

1. Create a temporary/new repository from the verified snapshot and validate it.
2. Establish the fresh canonical history and immutable release identity.
3. Run the clean Project Factory and client-like GitLab sandbox proof again.
4. Decide whether the old source remains public, becomes private, or is archived.
5. Rename/hand off the canonical name and publish consumer migration guidance.
6. Migrate downstream repositories only through separate repository-scoped tasks.

Repository creation, rename, visibility, and redirect operations are explicit
owner/admin actions; this repository performs none of them automatically.
