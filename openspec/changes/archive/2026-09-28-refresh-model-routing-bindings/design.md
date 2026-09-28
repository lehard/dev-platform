## Decisions

- **Codex routine -> `gpt-6-luna`**: the efficient tier for focused high-volume work; routine is the read-only/bounded profile.
- **Codex standard -> `gpt-6-sol`**: GPT-6 has no Terra tier; Sol is the balanced-cost stable option and replaces the superseded `gpt-5.6-terra`. `R2` remains the default tier and Sol at `standard` does not raise assurance or verification policy.
- **Codex complex -> `gpt-6-sol`**: `gpt-6-astra` costs roughly 2.5x Sol and is not needed as the default frontier binding; revisit if `R3` escalations show Sol inadequate. Tier separation for complex vs standard stays a tier/effort concern, not a model-id concern.
- **Claude**: unchanged aliases. They are the only form the Claude Code Agent handoff accepts and they follow the current generation.
- **Evidence**: calibration has 28 verified observations only for `gpt-5.6-terra` and none for candidate models, so adoption is a dogfood-first change on the central checkout; `routing-calibration` and `efficiency-baseline` then report the new models under their own `provider:model` keys without new machinery.
- **Rollback**: reverting the three binding sites and releasing through the existing immutable release/promotion path restores the prior routing; no state migration is involved.
