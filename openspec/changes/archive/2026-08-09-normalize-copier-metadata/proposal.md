# Normalize Copier metadata before rollout validation

## Why

The third live Planner Lab rollout reached a conflict-free exact-version update to `v1.2.2`, synchronized platform metadata, and passed platform doctor, but strict `git diff --check` stopped on a trailing blank line emitted in `.copier-answers.yml` by Copier itself.

This is machine-owned metadata formatting, not downstream project ambiguity. Weakening whitespace validation globally would hide real problems, so rollout should normalize only the Copier answers file before strict validation.

## What changes

- Canonicalize `.copier-answers.yml` to exactly one terminating newline after Copier update.
- Keep `git diff --check` strict for the whole downstream diff.
- Add regression coverage for extra trailing blank lines.

## Non-goals

- No generic whitespace auto-fixing in project files.
- No relaxation of conflict or project-check gates.

## Definition of Done

- Copier-generated trailing blank lines cannot block an otherwise valid rollout.
- Project whitespace errors remain blocking.
- Platform CI and strict OpenSpec validation pass.
