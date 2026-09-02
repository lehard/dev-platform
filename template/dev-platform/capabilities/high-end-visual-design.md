# High-end visual design

Specialized visual profile for surfaces whose **stated goal** is an ambitious,
distinctive visual identity: marketing and landing pages, brand and product
launch pages, portfolios, and campaign microsites.

## Applicability gate — read first

Apply this profile only when a project or task has **explicitly selected** it for
a matching surface.

Do **not** apply it — and do not let it become a default — for:

- dashboards, admin consoles, settings, and internal B2B tools;
- data-dense or workflow-heavy product UI;
- accessibility-first, public-sector, or regulated flows;
- any surface where the project design system or product requirements already
  fix the visual language.

For those, use the general `frontend-design` capability (or the project's own
design system) instead. If you are unsure which case you are in, you are not in
this one.

## Precedence

Everything in `frontend-design`'s precedence section applies here unchanged:
project product requirements, the project design system, accessibility and
regulatory constraints, and accepted OpenSpec all outrank this profile. It
changes no product intent, creates no managed work, and adds no runtime
dependency.

## What this profile adds on top of `frontend-design`

- **Higher design variance by default.** Asymmetry, offset grids, layering, and
  overlap instead of centered symmetry — tuned down when the brief reads calm or
  editorial.
- **Distinctive type.** Reach past `Inter`/system defaults for the display face;
  set deliberate tracking and a wide weight range for hierarchy.
- **One accent, considered.** A single accent color under ~80% saturation over a
  tinted neutral base; no multi-accent palettes and no unbroken 45° gradients.
- **Layout-archetype variety.** Vary the feature/section structure (zig-zag,
  asymmetric grid, horizontal scroll, editorial columns) rather than repeating
  one card row.
- **Orchestrated motion.** A page-load or scroll-driven sequence that serves the
  subject, always with a reduced-motion fallback.
- **A signature element.** One memorable thing that embodies the brief; keep
  everything around it disciplined.

## Non-negotiable floor

Responsive to mobile, visible keyboard focus, reduced motion respected, real
draft copy, and no regression of any project accessibility or functional
requirement. Ambition never buys an exception to these.

This capability is instruction-only. It installs nothing, accesses no
credentials, and authorizes no production or runtime change.
