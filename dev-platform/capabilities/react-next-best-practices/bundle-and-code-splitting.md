# Rule group: Bundle size and code-splitting

Applies to work that adds a dependency or a heavy client feature.

- Before adding a client dependency, check its cost and whether the platform or a
  smaller library already covers the need. Prefer server-side work that ships no
  client JavaScript.
- Split large, rarely-used, or below-the-fold client features with `next/dynamic`
  or `React.lazy` + `Suspense`. Load an editor, chart, map, or modal on demand.
- Keep heavy libraries out of shared layout and root client components; they are
  paid for on every route.
- Import named exports directly so a large package tree-shakes; avoid
  `import * as` for big modules and avoid a barrel file that pulls in the whole
  package.
- Move purely server-side helpers into server-only modules so they never enter a
  client chunk.
- Load third-party scripts with the framework's script component and the right
  strategy instead of a raw blocking `<script>`.
- Measure with the build output or a bundle analyser before and after; state the
  delta rather than guessing.

If the project has a bundle budget or an approved dependency list, that governs.
