## Context

- Plain template files render byte-identically downstream, so `sha256(template file)` equals `sha256(downstream file)` for an unmodified install; `.jinja` files depend on project answers and are out of hotfix scope.
- `.copier-answers.yml` `_commit` and `.dev-platform.toml` `platform_version` identify the installed release; `platform_doctor.py` already reports Copier update conflicts and platform version coherence.
- `agent_friction.py` is the existing platform-friction channel; its event ids are machine-local but referenceable from the record.

## Decisions

1. **Detection by manifest digest, declaration by record.** The release step writes `platform-manifest.json` (path -> sha256, plus the release version). A path diverges when its current digest differs from the manifest. Divergence is allowed only when a record entry covers that path and its `patched_sha256` equals the current digest; any other state fails. This keeps the mechanism local and stateless: no registry beyond a project-owned TOML file under version control.
2. **Hotfix scope is the hotfixable list from the change-class contract.** A record entry for a protected path, a `.jinja`-rendered file or an unknown path fails. The protected-surface file and the manifest are themselves protected; editing either is reported as a protected touch.
3. **Temporary by construction.** An entry carries `platform_version`; after a Copier update the installed version differs and the entry is reported stale until reviewed. Copier's own three-way merge conflict (if any) is surfaced by the existing conflict check. The check never deletes or rewrites an entry.
4. **Regression evidence is mandatory and referenced.** The entry names a test path that must exist; the PR review (independent review gate, unchanged) judges its adequacy. The check verifies presence only and states so; it does not claim the test proves the fix.
5. **Friction is mandatory.** The entry must name an `agent_friction.py` event id, so the platform learns of every hotfix through the existing review path. The id's existence is checked when the machine-local log is readable; an unreadable log is reported, never silently accepted (no fallback).
6. **Where it runs.** `platform_doctor.py` and the project's `full_commands` trigger set include the check; because the manifest and check are platform-owned and protected, a project cannot edit them away without the check failing.
7. **Release preparation owns the manifest.** `release_intent.py`/the release step regenerates it, and a platform test fails when the manifest does not match the template tree, so a release cannot ship a stale manifest.

## Risks and mitigations

- *A hotfix could weaken a guarantee indirectly (patching an unprotected helper used by a protected gate).* Mitigation: the protected globs cover script groups; the contract tests assert protected scripts import only protected or explicitly vetted helpers, and independent review of the hotfix PR remains mandatory and non-disableable.
- *Agents could forge the record.* Mitigation: the record is checked against actual digests, the regression test path and the friction id; it grants nothing on protected paths, and the PR still needs independent review.
- *Copier update meets a hotfix.* Mitigation: stale-record failure is explicit and actionable; automatic resolution is a separate follow-up (non-goal).
