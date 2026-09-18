# Public distribution cutover

The public product is cut over from a verified sanitized snapshot, not by
rewriting historical references that are merely project or operator names.
Run `python3 scripts/public_distribution.py audit`, render a clean default
project, and complete the GitLab sandbox proof before preparing a deterministic
tar snapshot with `snapshot --output <path>`.

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
