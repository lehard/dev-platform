# DEC-0007: Meet the OpenSpec requirement-length limit by splitting requirements

- **Status:** Current
- **Scope:** OpenSpec version and the form of accepted requirements in `openspec/specs/`
- **Decision date:** 2026-10-31
- **Authored against revision:** `9390a100eaae7e143c66dfe8fd54847a2a68b17b`
- **Supersedes:** None
- **Superseded by:** None

## Accepted current decision

The platform follows the upstream path to OpenSpec 1.15.0. From 1.14.1 a requirement description over
500 characters is a warning, and `openspec validate --strict` fails on it. We split our long requirements
with the procedure the 1.15.0 specs instruction gives: in a change made for that purpose, keep the MODIFIED
header and every scenario, cut the description to one behavior without changing its meaning, and add each
removed behavior as its own ADDED requirement with its own scenarios. The limit is measured on the
description in UTF-16 units; scenarios are not counted.

In practice:

- the split runs in small managed changes of about 12–18 specs each, one at a time, and review checks
  that meaning is preserved;
- the OpenSpec pin moves from 1.13.2 to 1.15.0 in the last change, once `openspec validate --all --strict`
  is green on 1.15.0;
- no exemption or filter for `REQUIREMENT_TOO_LONG` is added; a new ADDED requirement in any change stays
  at 500 characters or fewer, which 1.15.0 checks under `--strict`.

## Rejected and deferred alternatives

- **B — repository-owned gate over `--strict`** (non-strict validation plus `--json`, failing on every
  finding except `REQUIREMENT_TOO_LONG`): rejected. It would drop an upstream rule through our own
  filter; the owner prefers the upstream contract.
- **C — stop at 1.14.0**, where `--strict` still passes: rejected. It misses the 1.14.1+ fixes the upgrade is
  for (artifact path containment, removed-requirement verification, archive content-loss warnings).
- **D — defer the upgrade**: rejected; the split is mechanical enough to do in portions.

## Evidence

- Upstream issue [Fission-AI/OpenSpec#1976](https://github.com/Fission-AI/OpenSpec/issues/1976) and
  [Fission-AI/OpenSpec#2020](https://github.com/Fission-AI/OpenSpec/pull/2020) (the strict failure and the
  split procedure).
- On 2026-10-31, 1.15.0 `validate --specs --strict` reported 229 long requirements in 37 of 51 specs;
  1.13.2 and 1.14.0 pass. The limit `MAX_REQUIREMENT_TEXT_LENGTH = 500` is hard-coded.

## Revisit triggers

- Upstream makes the limit configurable or changes how it is measured.
- A split cannot state a behavior in 500 characters without changing its meaning.
