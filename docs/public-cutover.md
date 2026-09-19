# Public distribution cutover

The public product is cut over from a verified sanitized snapshot, not by
rewriting historical references that are merely project or operator names.
Run `python3 scripts/public_distribution.py audit` and
`python3 scripts/public_distribution.py history-audit`, render a clean default
project, and complete the GitLab sandbox proof before preparing a deterministic
tar snapshot with `snapshot --output <path>`. The current-tree audit covers
the exact product candidate set used by that snapshot. It permits only the
canonical `lehard/dev-platform` product identity; a companion Development
Backlog repository, other personal downstream, fleet, and bot references are
operator state, not product identity, and must be replaced with synthetic
examples in shipped source. The candidate set is a canonical, self-contained
source checkout, not a reduced runtime export: `tests/` and accepted
`openspec/specs/` plus current OpenSpec lifecycle configuration ship so a
fresh clone stays developable, testable, and spec-driven from its first
commit. Maintenance-only history (`openspec/changes/archive/`), local
agent/runtime state, an in-flight change's own `.managed-task.json` task
provenance, and the central checkout's own `.dev-platform.toml` are
deliberately excluded from the product candidate set. The shipped template
remains the portable configuration surface.

## External one-shot cutover policy

Known project-specific compatibility markers (private downstream code names)
and any prohibited repository outside the `lehard/` owner are migration
knowledge, not product source, and are never encoded in
`scripts/public_distribution.py` itself -- not even through split literals.
Supply them for one-shot pre-cutover sanitization with an explicit external
policy file:

```bash
python3 scripts/public_distribution.py audit --cutover-policy /secure/operator/cutover-policy.json
python3 scripts/public_distribution.py snapshot --output <path> --cutover-policy /secure/operator/cutover-policy.json
```

The policy is a small versioned JSON document, kept outside the repository
(or, if placed inside it, automatically excluded from the candidate set and
snapshot):

```json
{
  "version": 1,
  "prohibited_repositories": {"legacy_downstream": "acme/legacy-service"},
  "compatibility_markers": {"legacy_merge_partner": "\\bSomePrivateCodeName\\b"}
}
```

`--cutover-policy` is optional; omitting it runs the reusable public audit
alone, which is what the fresh canonical public repository does after
cutover (it never needs the old operator's deny data). An explicitly supplied
policy that is missing, unreadable, or fails schema validation fails the
command closed with no snapshot produced. Findings from either the audit
receipt or a printed error identify the finding's label and file path only;
neither ever repeats the raw prohibited-repository string or marker pattern
from the policy, and the receipt's `policy.cutover_policy` field records only
the policy's basename, schema version, and content digest.

## Operator handoff checklist

Before the next real managed fleet rollout on this installation, confirm the
following external, non-shipped configuration is in place (see
`docs/operator-config.example.toml` for the full shape and
`python3 scripts/operator_doctor.py` for validation):

1. `[development_backlog]` -- the real `repository`, `project_label`,
   `default_priority`, `project_owner`, and `project_number` for this
   operator's Development Backlog installation.
2. `[rollout] registry_path` -- the real managed-projects registry path, and
   `bot_login` if fleet rollout mutates repositories under a bot identity.
3. `[rollout.legacy_harness_migrations]` -- only if a live downstream
   repository is still mid-migration off a legacy pre-platform publication
   harness; omit entirely otherwise.

Run `python3 scripts/operator_doctor.py` to validate the configured
`[rollout] registry_path` before any real fleet mutation. `[development_backlog]`
is validated at managed-authoring time (`scripts/managed_task.py`) and
`[rollout.legacy_harness_migrations]` at rollout time (`scripts/rollout_project.py`);
each fails closed -- rollout applies nothing to a downstream repository it
cannot match to configured continuity data rather than falling back to a
hidden public default. None of these real values are committed to public
source -- they live only in the operator's own `config_path`/`config_env`
file referenced by `[operator]` in `.dev-platform.toml`.

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
