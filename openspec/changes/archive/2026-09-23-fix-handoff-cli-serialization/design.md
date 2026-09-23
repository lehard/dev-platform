# Design: Successful handoff output

Keep the existing module-level `json` import and remove the `aggregate` branch-local import. Exercise `main()` through its CLI boundary with a mocked successful `materialize_handoff` result, rather than only calling the adapter function; this catches Python local-name binding regressions without external GitHub writes. Preserve the existing real parent/child verification inside the adapter.
