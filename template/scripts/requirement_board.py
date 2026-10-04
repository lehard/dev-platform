#!/usr/bin/env python3
"""Project the read-through Requirement stage onto its human-facing card.

This module owns only nonterminal projection. Shared publication owns the
terminal Done transition after its exact protected-merge proof.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import managed_project_status
import requirement_intake


class RequirementBoardError(RuntimeError):
    pass


def desired_nonterminal_status(progress: dict[str, Any]) -> str:
    stage = progress.get("stage")
    if stage in {"pre-authoring", "design", "ready", "implementation", "done"}:
        # Child-level Done does not prove a merged Requirement candidate.
        return "In progress"
    if stage in {"human-decision", "blocked", "unknown"}:
        return "Blocked"
    raise RequirementBoardError(f"unsupported Requirement progress stage: {stage!r}")


def reconcile_nonterminal(root: Path, *, requirement: str) -> dict[str, Any]:
    projection = requirement_intake.aggregate(root, requirement=requirement)
    if projection.get("requirement") != requirement:
        raise RequirementBoardError("Requirement projection identity differs from requested Issue")
    progress = projection.get("progress")
    if not isinstance(progress, dict):
        raise RequirementBoardError("Requirement progress evidence is unavailable")
    desired = desired_nonterminal_status(progress)
    observation = managed_project_status.observe(root, source_issue=requirement)
    if observation is None or observation.current_status is None:
        raise RequirementBoardError("Requirement has no readable primary Project card")
    if observation.current_status == desired:
        return {"requirement": requirement, "stage": progress["stage"], "status": desired, "changed": False,
                "reason": progress.get("reason")}
    changed = managed_project_status.reconcile(root, desired, source_issue=requirement)
    if changed is None:
        raise RequirementBoardError("Requirement primary Project card disappeared during reconciliation")
    return {"requirement": requirement, "stage": progress["stage"], "status": changed.current_status,
            "changed": changed.changed, "reason": progress.get("reason")}
