# UI Quality Review

Use this capability when a human asks for a UI or web-quality review, an
accessibility pass, or a check that a user-facing change behaves correctly for
keyboard, assistive-technology, form, or small-screen users. It is an advisory,
read-only critic. It never redesigns the surface and never opens work items.

## Review boundary

1. Record the reviewed surface: repository, the full immutable revision
   (`git rev-parse HEAD` or an explicitly supplied revision), the routes,
   components, or files in scope, and anything explicitly excluded. Do not
   review against a moving branch name alone.
2. Read the project design system, component library, accessibility rules, and
   accepted OpenSpec behaviour first. They are authoritative; this review only
   helps apply them. A conflict between this guidance and a project rule is
   resolved in the project rule's favour and reported as such.
3. Gather evidence at each candidate location: the markup or component source,
   the roles and names it produces, its keyboard and focus behaviour, its form
   semantics, and its behaviour at a narrow viewport. A screenshot or a single
   line of markup is a lead, not a confirmed defect.

## What to examine

- **Accessibility semantics.** Landmarks, heading order, accessible names,
  roles, `alt` text, colour-contrast evidence, and correct use of ARIA only
  where a native element cannot express the intent.
- **Keyboard and focus.** Every interactive control is reachable and operable by
  keyboard, focus order follows reading order, focus is visible, focus is
  managed across dialogs and route changes, and no focus trap exists outside a
  modal.
- **Forms.** Programmatically associated labels, validation and error messages
  that are announced and linked to their field, required-field indication that
  is not colour-only, and a submit path that works without a pointer.
- **Responsive and user-visible behaviour.** Content and controls remain usable
  from mobile width upward, no horizontal scroll trap, reduced-motion is
  respected, loading and error states are real, and hit targets are adequate.
- **Web-quality issues.** Broken or ambiguous link text, images without
  dimensions causing layout shift, and content that depends only on hover.

## Findings

Return a Markdown report (outside application code, or directly) with this shape:

```markdown
# UI Quality Review — <date>

- reviewed surface: <repository, routes/components, exclusions>
- exact revision: `<full commit SHA>`
- authoritative rules consulted: <design system, a11y policy, OpenSpec>
- evidence gathered: <files, rendered output, tools, manual checks>

## Findings

### UQ-001 — <short evidence-backed title>

- category: <accessibility | keyboard/focus | forms | responsive | web-quality>
- location: `<path>:<symbol-or-line>` (and route if relevant)
- evidence: <the markup, role/name output, keyboard result, or viewport result>
- severity: <blocker | serious | minor> — <who is affected and how>
- uncertainty: <what was not verifiable, or a competing explanation>
- recommendation: <smallest change that resolves it, no redesign>

## Healthy checks

- <surface area that was verified correct — required so a heuristic does not over-report>

## Boundary

No code, Issue, Backlog item, or managed task was created by this review.
Repeated critical requirements are promoted to project tests only by a separate
accepted project decision.
```

## No unsolicited redesign

Report only defects that evidence supports against an authoritative rule or an
established accessibility norm. Do not propose a visual restyle, a new layout, a
new design language, or an aesthetic preference. If the surface is healthy, say
so plainly and list what was checked; do not manufacture cosmetic work to fill
the report.

## Precedence

In order of authority: (1) project product requirements and accepted OpenSpec
behaviour; (2) the project design system, brand guide, or component library;
(3) accessibility, regulatory, and functional-testing requirements; (4) this
capability's generic checks. This review shapes how quality is assessed, not
what the product is.

## Safety boundary

Instruction-only and read-only. Do not modify repository files, create commits,
create or edit Issues, create a Backlog item or managed task, dispatch an agent,
change a design system, or start a redesign. It installs nothing, accesses no
credentials, and authorizes no production or runtime change. Findings are
advisory and do not by themselves block a merge.
