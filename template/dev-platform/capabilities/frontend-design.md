# Frontend design

Use this capability for a **general** UI-quality pass: creating a new user-facing
surface, a substantial visual redesign, or a dedicated effort to make an existing
UI feel intentional rather than templated. It does not apply to routine frontend
code edits (a copy tweak, a prop rename, a spacing nudge) or to backend and other
non-UI work.

## Precedence

This guidance is subordinate. When any of the following exists, it wins and this
capability only helps you apply it well:

1. Project product requirements and accepted OpenSpec behavior.
2. A project-owned design system, brand guide, or component library.
3. Accessibility, regulatory, and functional-testing requirements.

This capability never changes product intent, never creates backlog or spec work,
and adds no application runtime dependency. It shapes how the UI is built, not
what the product is.

## Principles

- **Intentional direction.** Name the subject, its audience, and the page's one
  job before designing. Make deliberate palette, typography, and layout choices
  that are specific to this brief instead of reaching for a default look.
- **Typography carries personality.** Pair display and body faces on purpose and
  set a clear type scale with intentional weight and spacing.
- **Structure encodes meaning.** Numbering, eyebrows, dividers, and labels should
  reflect something true about the content, not decorate it.
- **Motion serves the subject.** Prefer one orchestrated moment over scattered
  effects; respect reduced-motion preferences.
- **Match complexity to the vision.** Maximalist directions need elaborate
  execution; minimal directions need precision in spacing, type, and detail.
- **Restraint and self-critique.** Spend boldness in one signature element and
  keep the rest quiet. Review the plan against the brief before building and cut
  anything that reads as a generic default.
- **Words are design material.** Name things by what the user controls, use
  active voice, keep terms consistent through a flow, and treat empty and error
  states as direction rather than mood.

## Generic AI-UI failure modes to avoid

Unless the brief or the project design system explicitly calls for it: the
purple/blue "AI gradient", a centered hero over a dark mesh, three equal feature
cards, glassmorphism on everything, infinite looping micro-animations, `Inter` +
`slate-900` as the unconsidered default, uniform border-radius everywhere, fake
round numbers, Lorem Ipsum, and Title Case on every header.

## Quality floor

Responsive down to mobile, visible keyboard focus, reduced motion respected,
real draft copy rather than placeholders. Build to this floor without announcing
it.

This capability is instruction-only. It installs nothing, accesses no
credentials, and authorizes no production or runtime change.
