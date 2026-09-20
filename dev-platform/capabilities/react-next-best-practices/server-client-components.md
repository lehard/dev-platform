# Rule group: Server vs Client Components

Applies to Next.js App Router work that decides where a component runs.

- Default to Server Components. Add `"use client"` only when the component needs
  state, effects, browser APIs, or event handlers.
- Put the `"use client"` boundary as low in the tree as possible. A client
  parent forces every imported child into the client bundle.
- Pass Server Components into Client Components as `children` or props instead of
  importing them across the boundary, so server-only code stays on the server.
- Keep secrets, tokens, and large server-only dependencies out of any module
  that a client component imports.
- Fetch data in the Server Component and pass plain serialisable props down.
  Only props that cross the boundary must be serialisable.
- Prefer reading a promise with `use()` in a Client Component over an effect that
  refetches what the server already has.
- `Context` providers are client components; mount them once near the root, not
  per route segment.

If the project sets its own rendering conventions or a different framework
version behaves differently, follow the project.
