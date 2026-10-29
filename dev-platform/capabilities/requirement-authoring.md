# Requirement authoring

Use this standard whenever you **write or materially change the body of a Business Requirement**: on "зафиксируй" / "добавь в бэклог" / "создай задачу", or when an accepted decision changes an existing Requirement. It applies identically to a repository agent (Claude, Codex) running `requirement_intake.py create`, and to a ChatGPT Project writing the same Issue through connected GitHub. It prepares the **content**; the Issue format, routing, labels, Project membership and children block are owned by `docs/engineering/task-intake.md` and are not changed here.

A Requirement is the **current agreed product contract**, not a summary of the conversation. A new agent given only the Requirement and the materials it directly references must be able to say what result is required, which decisions are fixed, how much freedom it has, which constraints matter and how acceptance is observed. Length follows content: lose nothing important for brevity, write nothing empty to fill a template.

This is an author's working discipline. It adds no stage, gate, status, validator, scorecard, approval, interview, storage or per-project setting, and it does not start implementation.

## 1. Read everything, then classify

Use the whole relevant conversation, attached or linked materials and available authoritative product context, not only the last message. Sort what you find:

- **Accepted and still in force** — requirements the human agreed to.
- **Superseding refinements** — an explicitly accepted later decision replaces the earlier one.
- **Examples and references** — illustrations, mockups, sample wording.
- **Rejected or hypothetical** — dropped options, agent suggestions, quotations, brainstorms.
- **Genuinely open** — material questions nobody has settled.

Only explicit acceptance makes something a requirement. The last option mentioned, an agent's proposal, a quote or a hypothesis is not acceptance. If material versions are incompatible and you cannot tell which was accepted, ask (section 6); do not pick one.

## 2. Write the current decision, not the history

State the agreed result affirmatively. Do not narrate "first A, then B, then B was dropped" when the final state is enough. Keep history only when its result is an **active boundary or prohibition**; then write the boundary and its material condition ("Do not X when Y"), not the negotiation. Do not widen the request: a specific prohibition or local behavior stays that, with no new global policy, neighboring scenario or convenient extra feature. A new substantial product idea is a proposal until the human accepts it.

## 3. Carry every material detail across

Whatever is already defined and material goes into the Requirement without loss: actors, roles, rights and the contexts that bound them; scenarios in their order, transitions, important exceptions and negative paths; agreed section, button and field names and input/answer rules; exact user-facing text and any permitted wording; invariants for safety, truthfulness, compatibility, money and data; visual requirements, information hierarchy and interactions; accepted delivery and acceptance conditions; and explicit exclusions. "Make it convenient / nice / high quality" never replaces an exact decision that was already made.

## 4. Make binding visible, in plain words

Show which of three levels each material point has, through wording rather than a new format:

1. **Fixed** — exact text, order, value, rule or property ("verbatim", "exactly", "always"); not changed without re-agreement.
2. **Meaning fixed, execution variable** — an example, base wording or set of mandatory properties ("must convey…", "for example…"); editorial and UX detail may vary while the accepted meaning and constraints hold.
3. **Delegated** — immaterial or undefined detail the executor decides inside the accepted corridor without changing the observable result.

Silence is not blanket freedom: delegation never allows changing product meaning, safety boundaries, data, rights or accepted scenarios. Equally, do not demand agreement on every color, spacing, function name or ordinary error handling that does not change material behavior.

The levels hold on the whole path to implementation. ADD and OpenSpec keep each point at the level written here and never bind it more tightly; see "Carry Requirement binding levels into OpenSpec" in [docs/engineering/openspec-workflow.md](../../docs/engineering/openspec-workflow.md).

## 5. Preserve references and be honest about gaps

If the discussion supplied a screenshot, mockup, document, link or other reference, keep it **reachable by the executing agent** through a stable, permitted channel and say which of its properties are mandatory (layout, hierarchy, wording, behavior). If the executor cannot reach an attachment, say it is unavailable and record what is known from it; never substitute a link to a changing site root. Do not copy private conversations, secrets, unreachable personal files or whole external documents into a public repository.

When the work is a second or later attempt at a problem that already has a friction root issue, link that issue in `Context` and name the earlier attempts with what each left unsolved, so the executor does not repeat a rejected path.

Place content in the existing sections only — `Outcome`, `Context`, `Acceptance evidence`, `Target repository`, `Exclusions`. Acceptance evidence names concrete observable results and, where it matters, the successful, failing and forbidden behavior; it does not restate the goal. Keep technical design, file plans and OpenSpec content out; ADD and OpenSpec own those later.

## 6. Ask only about unresolved material choices

Before writing, reconcile what the conversation, materials and authoritative context already answer. Ask the human only if proceeding would force you to decide something that materially changes the product result, rights, money or data invariants, essential scope, or the meaning of an earlier decision.

- Keep questions brief and grouped — normally one to three per pass — with the options and their consequences where that helps.
- Do not re-ask what was answered, ask technical ADD/OpenSpec questions, require empty sections or run a mandatory interview.
- If only minor detail is missing, record the accepted result and delegate the detail; do not delay.
- If a critical choice stays unresolved, never write an invented decision or claim agreement. Ask before fixation, or keep the idea as an unaccepted item under the existing Incubator contract.

This pre-fixation check does not replace the later evidence-first ADD/domain resolution, and it never substitutes for the product owner.

## 7. Check before writing and after material edits

Run six quick questions on the whole Requirement:

- **Coverage** — are the agreed material decisions and materials kept?
- **Consistency** — do Outcome, scenarios, Exclusions and Acceptance evidence agree, with no old rule left beside a new one?
- **Scope** — is anything added that was not asked for?
- **Autonomy** — is any fixed decision handed to the executor as free choice?
- **Portability** — can an agent without this chat find every source and follow the scenario?
- **Truthfulness** — are links, materials, facts and the degree of agreement real?

When a decision changes, rewrite the **entire current Requirement** — Outcome, scenarios, Exclusions and Acceptance evidence together — instead of appending a "new decision" note over old text. Never hand-edit the children block, lifecycle-owned markers or Project state; the existing Requirement revision binding and pre-authoring freshness handle a changed Requirement.

## Representative cases

**Long discussion.** The human settled the empty-state text word for word, the order "filter → list → detail" and that only managers can export. The Requirement quotes the text as *verbatim*, states the order and the export right as fixed, and delegates spacing and icon choice. It does not say "show a friendly empty state".

**Superseded option.** Three layouts were discussed; the human accepted the second, then ruled that exports must stay manager-only. The Requirement describes the second layout and the manager-only rule. It does not recount the other layouts, and its Acceptance evidence no longer requires the earlier all-users export check.

**Reference.** The human attached a mockup the executor can open. The Requirement links that file at its stable location and says the header hierarchy and button wording are mandatory while exact pixel offsets are not. If the attachment were inaccessible, it says so and lists what is known instead of linking the site's home page.

**Local prohibition.** "Do not email customers after hours" stays a rule about that email path. It does not become a company-wide notification policy.

**Compact request.** "Rename the Export button to Download CSV" yields a short Requirement with the exact label and a one-line acceptance check: no questionnaire, no empty sections.

**Unresolved fork.** Whether refunds may exceed the captured amount changes money invariants and is not answered anywhere: ask one brief question with the consequence of each answer instead of choosing.
