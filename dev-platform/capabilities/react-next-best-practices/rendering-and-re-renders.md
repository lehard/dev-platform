# Rule group: Rendering and wasted re-renders

Applies to work on component render behaviour and interactivity.

- Derive values during render instead of storing them in state and syncing with
  an effect. Redundant state is the most common cause of extra renders and bugs.
- An effect is for synchronising with an external system (network, DOM,
  subscription, timer). It is not for transforming props into state or for
  responding to a user event — do that in the event handler.
- Lift state only as high as it must go. State high in the tree re-renders every
  descendant; colocate it with the components that use it.
- Give list items a stable, data-derived `key`, never the array index for a list
  that can reorder or filter.
- Reach for `useMemo` / `useCallback` / `React.memo` only with evidence of a real
  cost (a measured expensive computation, or a memoised child that actually
  re-renders). Do not wrap everything by default.
- Keep context values stable and split contexts by update frequency so a
  fast-changing value does not re-render consumers of a slow-changing one.
- Prefer uncontrolled inputs or local state for high-frequency input; do not
  round-trip every keystroke through a global store.

If the project's state-management library prescribes a different pattern, follow it.
