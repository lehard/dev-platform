# Frontend design capabilities

Frontend design help is delivered as **opt-in optional engineering capabilities**,
not as platform-wide policy. They ride the shared lifecycle described in
[Optional engineering capabilities](engineering-capabilities.md): one canonical
descriptor per capability in `dev-platform/capabilities/<id>.toml`, project opt-in
in `dev-platform/capabilities.toml`, derived provider skills only for selected
capabilities. This document adds only the design-specific applicability, profile
semantics, and precedence rules.

## Why opt-in

AI-generated frontend often collapses into a generic look, but no single
aesthetic is right for every project: a marketing launch page, a consumer app,
and an internal B2B console want different visual modes. A hard visual skill
imposed as a global default would turn one upstream author's taste into platform
policy. So design guidance is available to projects and tasks that choose it and
is absent everywhere else.

## Capabilities

| Capability | Role | Applies to | Does not apply to |
| --- | --- | --- | --- |
| `frontend-design` | General | New UI surfaces, substantial redesigns, dedicated UI-quality passes | Routine frontend edits (copy, prop, spacing); backend and other non-UI work |
| `high-end-visual-design` | Specialized profile | Explicitly selected marketing, landing, brand, launch, campaign, and portfolio surfaces that want an ambitious distinctive identity | Dashboards, admin consoles, data-dense or workflow-heavy product UI, accessibility-first / public-sector / regulated flows — use `frontend-design` or the project design system instead |

Both are `instruction-only` and `auto+explicit`. Neither is listed in
`capabilities.toml` by default, so nothing materializes until a project runs
`python3 scripts/capability_manager.py enable <id>`.

### Specialized profiles are never a silent default

`high-end-visual-design` carries an explicit applicability gate at the top of its
instruction file and a declared non-applicability list in its descriptor. Because
selection is project-owned opt-in and the default `enabled` list is empty, a
specialized profile cannot become the default for a dashboard or B2B UI without a
deliberate project choice. If a project wants it only for its marketing surface,
that is a project decision recorded in `capabilities.toml`, not a platform one.

## Precedence

When a design capability is active, it is still subordinate. In order of
authority:

1. Project product requirements and accepted OpenSpec behavior.
2. The project-owned design system, brand guide, or component library.
3. Accessibility, regulatory, and functional-testing requirements.
4. The design capability's generic heuristics.

A design capability shapes how UI is built. It never changes product intent,
never creates backlog or spec work, never becomes a second planning lifecycle,
and adds no application runtime dependency. It is agent-facing development
tooling.

## Triggering discipline

Design context loads for real create / redesign / UI-quality work, not for every
frontend code edit and not for backend work. The bounded fixtures in
`dev-platform/evals/frontend-design-pilot.json` and
`dev-platform/evals/high-end-visual-design-pilot.json` encode positive create /
redesign / UI-quality prompts and hard-negative backend, data-table, settings,
and (for the specialized profile) dashboard / B2B / regulated control prompts.
They are deterministic CI evidence of the intended trigger boundary, not a claim
about a provider's live routing.

## Provenance — bounded adaptation

Dev Platform vendors no upstream skill files. Each capability instruction file is
an independent, bounded adaptation of widely-published design principles, and its
descriptor records the reviewed upstream source, revision, and license so the
effective guidance cannot drift when a mutable upstream branch changes.

| Capability | Reviewed upstream | Revision | License | Treatment |
| --- | --- | --- | --- | --- |
| `frontend-design` | [`anthropics/skills`](https://github.com/anthropics/skills) `skills/frontend-design/SKILL.md` | `53048666b05b4799081517d00e09e0a2dd688678` | Apache-2.0 (`skills/frontend-design/LICENSE.txt`) | Adapt — bounded principles (intentional direction, typographic hierarchy, structure encodes meaning, purposeful motion, restraint, writing as design material, generic-AI-UI failure modes, quality floor) rewritten provider-neutrally with an explicit precedence section. |
| `high-end-visual-design` | [`leonxlnx/taste-skill`](https://github.com/leonxlnx/taste-skill) `skills/taste-skill/SKILL.md` (marketplace alias `design-taste-frontend`) and `skills/redesign-skill/SKILL.md` (alias `redesign-existing-projects`) | `ccbc15639c97057cbfcf32ecebc38ef716e4bb37` | MIT (`LICENSE`) | Adapt — the ambition/anti-default/layout-variety/orchestrated-motion/signature ideas and the "not dashboards, not data tables" scope, rewritten as a bounded profile layered on `frontend-design` with a hard applicability gate. Dial mechanics, framework package maps, and other implementation specifics are not adopted. |

Updating a capability to a newer reviewed upstream is an explicit
`python3 scripts/capability_manager.py update <id>` with a refreshed descriptor
revision and content hash, reviewed like any other change.
