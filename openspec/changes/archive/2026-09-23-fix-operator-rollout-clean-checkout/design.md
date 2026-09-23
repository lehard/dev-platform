# Design: Let Copier author the selected answer

`rollout_project.py` receives a trusted boolean only from the validated private managed-project registry. It constructs the optional Copier `--data operator_integration=true` argument when that boolean is selected. Both `copier update` and fallback `copier recopy` receive the argument while the checked-out target is still clean.

Copier then renders the platform and writes `.copier-answers.yml` as its own normal update result. Existing bootstrap and config-contract assertions prove that the only operator table added is the generic environment-backed table. A regression test observes the Copier command and target cleanliness before it runs.
