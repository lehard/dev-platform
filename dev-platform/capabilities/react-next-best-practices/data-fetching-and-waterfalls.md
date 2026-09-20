# Rule group: Data fetching and request waterfalls

Applies to work that loads data for a React/Next view.

- Start independent requests together. Kick off the fetches first, then `await`
  them (or `Promise.all`), so they do not run in series.
- A request waterfall is when request B waits only because it is written after
  request A, not because it needs A's result. Fix it by hoisting or parallelising.
- Fetch where the data is used and let the framework dedupe identical requests
  within a render, rather than threading one result through many props.
- Choose caching deliberately: static data can be cached, request-specific or
  user-specific data must not be. State the revalidation interval explicitly
  rather than relying on a default.
- Stream slow, non-critical sections behind `Suspense` with a real fallback so
  the shell renders immediately; keep above-the-fold content out of a boundary
  that blocks it.
- Do not fetch in a Client Component effect for data the server can provide at
  render time.
- Handle the error and empty states next to the fetch, not several layers away.

If the project has its own data-layer contract, follow it.
