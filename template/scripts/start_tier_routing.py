#!/usr/bin/env python3
"""Provider-neutral managed-task start-tier rubric (R1/R2/R3).

Authoring records a recommended abstract start tier for a managed task
*before* any execution session starts. This module intentionally holds no
provider/model identity: concrete provider-local models remain replaceable
`[model_routing]` policy in `.dev-platform.toml`. It only decides/validates
the abstract tier and its mapping to the existing routine/standard/complex
execution-profile vocabulary used by `model_routing.py`.

R2 is the default production tier. R3 requires a concrete recorded hard
trigger from a bounded allow-list -- diff size, file count, public
visibility, blast radius or failure cost alone are not sufficient triggers.
R1 economy semantics are reserved but not recommended until a later
evidence-gated change enables them.
"""
from __future__ import annotations

from typing import Any

RUBRIC_VERSION = "v1"

TIERS: tuple[str, ...] = ("R1", "R2", "R3")
DEFAULT_TIER = "R2"
PRODUCTION_DISABLED_TIERS: tuple[str, ...] = ("R1",)

# Bounded allow-list of concrete reasoning-outcome-changing evidence classes.
# Diff size, file count, public visibility, blast radius and failure cost are
# deliberately excluded: those may raise assurance while staying at R2.
STRONG_TRIGGERS: tuple[str, ...] = (
    "unresolved_architecture",
    "unknown_diagnosis",
    "weak_verification_high_consequence",
    "novel_cross_system",
    "trustworthy_escalation_history",
    "prior_balanced_failure",
)

ROUTING_CONFIDENCE_VALUES: tuple[str, ...] = ("low", "medium", "high")
ASSURANCE_VALUES: tuple[str, ...] = ("standard", "high")
EFFORT_HINT_VALUES: tuple[str, ...] = ("low", "medium", "high")

ROUTING_RECEIPT_KEYS: tuple[str, ...] = (
    "recommended_start_tier",
    "rubric_version",
    "task_family",
    "routing_confidence",
    "assurance",
    "effort_hint",
    "strong_trigger",
)

_TIER_TO_PROFILE = {"R1": "routine", "R2": "standard", "R3": "complex"}


class StartTierError(RuntimeError):
    """An actionable start-tier rubric/authoring error."""


def recommend_start_tier(
    *,
    strong_trigger: str | None,
    task_family: str = "general",
    routing_confidence: str = "medium",
    assurance: str = "standard",
    effort_hint: str | None = None,
) -> dict[str, Any]:
    """Record a provider-neutral start-tier recommendation.

    ``strong_trigger`` must be a supported concrete hard-trigger category to
    select `R3`; without one, the recommendation is always the `R2` default.
    This function never returns `R1`: the reserved economy tier is not an
    automatic/recommended outcome of this rubric in its first production
    version.
    """
    if not task_family.strip():
        raise StartTierError("task_family must be a non-empty string")
    if routing_confidence not in ROUTING_CONFIDENCE_VALUES:
        raise StartTierError(f"routing_confidence must be one of {', '.join(ROUTING_CONFIDENCE_VALUES)}")
    if assurance not in ASSURANCE_VALUES:
        raise StartTierError(f"assurance must be one of {', '.join(ASSURANCE_VALUES)}")
    if strong_trigger is not None:
        trigger = strong_trigger.strip()
        if trigger not in STRONG_TRIGGERS:
            raise StartTierError(f"unsupported frontier hard trigger: {strong_trigger!r}; must be one of {', '.join(STRONG_TRIGGERS)}")
        tier = "R3"
    else:
        trigger = None
        tier = DEFAULT_TIER
    if effort_hint is None:
        effort_hint = "high" if tier == "R3" else "medium"
    elif effort_hint not in EFFORT_HINT_VALUES:
        raise StartTierError(f"effort_hint must be one of {', '.join(EFFORT_HINT_VALUES)}")
    return {
        "recommended_start_tier": tier,
        "rubric_version": RUBRIC_VERSION,
        "task_family": task_family.strip(),
        "routing_confidence": routing_confidence,
        "assurance": assurance,
        "effort_hint": effort_hint,
        "strong_trigger": trigger,
    }


def validate_routing_receipt(value: Any) -> dict[str, Any] | None:
    """Validate a routing receipt read back from a managed package/provenance.

    Returns ``None`` for an absent receipt (legacy packages authored before
    this rubric existed remain importable). Raises for a present-but-invalid
    receipt, including an `R3` claim without a supported concrete trigger --
    this is the defense-in-depth check against a hand-edited package.
    """
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != set(ROUTING_RECEIPT_KEYS):
        raise StartTierError("routing_receipt has an invalid shape")
    tier = value.get("recommended_start_tier")
    if tier not in TIERS:
        raise StartTierError(f"routing_receipt has an unsupported start tier: {tier!r}")
    if tier in PRODUCTION_DISABLED_TIERS:
        raise StartTierError(f"start tier {tier} is reserved and disabled for production recommendation")
    trigger = value.get("strong_trigger")
    if tier == "R3":
        if trigger not in STRONG_TRIGGERS:
            raise StartTierError("an R3 recommendation requires a concrete supported hard-trigger rationale")
    elif trigger is not None:
        raise StartTierError("strong_trigger must be null unless the recommended tier is R3")
    for key in ("task_family", "routing_confidence", "assurance", "effort_hint", "rubric_version"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise StartTierError(f"routing_receipt.{key} must be a non-empty string")
    if value["routing_confidence"] not in ROUTING_CONFIDENCE_VALUES:
        raise StartTierError(f"routing_receipt.routing_confidence must be one of {', '.join(ROUTING_CONFIDENCE_VALUES)}")
    if value["assurance"] not in ASSURANCE_VALUES:
        raise StartTierError(f"routing_receipt.assurance must be one of {', '.join(ASSURANCE_VALUES)}")
    if value["effort_hint"] not in EFFORT_HINT_VALUES:
        raise StartTierError(f"routing_receipt.effort_hint must be one of {', '.join(EFFORT_HINT_VALUES)}")
    return value


def title_prefix(tier: str) -> str:
    if tier not in TIERS:
        raise StartTierError(f"unknown start tier: {tier!r}")
    return f"[{tier}]"


def tier_to_profile(tier: str) -> str:
    """Map an abstract start tier to the existing execution-profile vocabulary.

    This mapping is the only bridge between the provider-neutral tier
    recorded at authoring and the routine/standard/complex profile that
    `model_routing.py` already uses to select a configured executor model.
    """
    if tier not in _TIER_TO_PROFILE:
        raise StartTierError(f"unknown start tier: {tier!r}")
    if tier in PRODUCTION_DISABLED_TIERS:
        raise StartTierError(f"start tier {tier} is reserved and disabled for production execution")
    return _TIER_TO_PROFILE[tier]
