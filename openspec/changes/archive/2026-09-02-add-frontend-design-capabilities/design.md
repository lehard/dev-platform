# Design: Reusable design help without a universal taste policy

## Decisions

1. **Capability mechanics come from #87.** Identity, provenance, project opt-in, provider-local materialization, dependencies and update/removal use the shared optional-capability contract.
2. **Opt-in, not default.** Design capabilities apply only to eligible projects/tasks; backend and non-design work should not load them.
3. **General plus specialized profiles.** A broad `frontend-design`-level capability is the general candidate; Taste/high-end/redesign profiles require explicit selection and suitability rules.
4. **Project rules win.** Product requirements, project design system, accessibility constraints and accepted OpenSpec override generic aesthetic guidance.
5. **Trigger discipline.** Capabilities load for creation, substantial redesign or UI-quality tasks, not every frontend code edit.
6. **Pinned provenance.** External skills are version/revision pinned or their bounded principles are adapted with source/license recorded through #87.
7. **No product authority.** A design skill can propose/shape implementation but cannot change product intent, create work or become a second planning lifecycle.
8. **No production dependency by default.** These are agent/development capabilities rather than runtime application dependencies.
