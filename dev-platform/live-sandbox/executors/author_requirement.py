#!/usr/bin/env python3
"""Author the pre-authoring chain of a two-child sandbox Requirement, run from the sandbox checkout.

ADD approval is a human decision and stays outside a scenario, so this fixture records it through the same platform
calls under a scenario identity. Everything from `execute_requirement.py advance` on is real.

argv: <requirement number> <bundle directory> <first change> <second change>.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "template" / "scripts"))

import add_intents  # noqa: E402
import orchestrate_pre_authoring as orch  # noqa: E402
import project_evidence  # noqa: E402

BASE = ROOT / ".claude" / "pre-authoring"


def worker_results() -> dict:
    current = project_evidence.inventory(ROOT)
    return {concern: {"version": 1, "confidence": "high", "conflicts": [], "unknowns": [],
                      "facts": [{"statement": f"{concern} fact", "evidence_refs": [dependencies[0]]}] if dependencies else [],
                      "provenance_ref": f"live-scenario:{concern}", "usage": {"model_calls": 0}}
            for concern, dependencies in current["dependencies"].items()}


def main() -> int:
    number, bundles, changes = sys.argv[1], Path(sys.argv[2]), sys.argv[3:5]
    requirement_id = f"requirement-{number}"
    orch.select_depth(ROOT, requirement_id=requirement_id, depth=orch.DEPTH_MATERIAL_DESIGN,
                      reason="Two independent fixture boundaries", base_dir=BASE)
    directory = orch.requirement_dir(BASE, requirement_id)
    snapshot, _ = project_evidence.build_snapshot(ROOT, prior=None, results=worker_results())
    orch._write_json(orch.snapshot_path(directory), snapshot)
    projection = snapshot["projections"]["project-context"]
    add_file = orch.add_path(directory)
    add = json.loads(add_file.read_text(encoding="utf-8"))
    if "prepared_by" in add:
        add["prepared_by"] = "live-scenario-preparer"
    add["evidence"] = [{"source": orch.snapshot_path(directory).relative_to(ROOT).as_posix(),
                        "kind": add_intents.EVIDENCE_KIND_SNAPSHOT, "digest": projection["digest"],
                        "snapshot_digest": snapshot["digest"], "snapshot_revision": snapshot["revision"],
                        "projection": "project-context", "projection_digest": projection["digest"],
                        "projection_status": projection["status"]}]
    add["elements"] = [{"id": f"element-{change}", "category": "boundary", "status": "new", "statement": f"Boundary of {change}"}
                       for change in changes]
    add_file.write_text(json.dumps(add), encoding="utf-8")
    add_intents.approve_add(ROOT, add_file, approved_by="live-scenario")
    intents_file = orch.intents_path(directory)
    add_intents.decompose(ROOT, add_path=add_file, out=intents_file)
    intents = json.loads(intents_file.read_text(encoding="utf-8"))
    intents["intents"] = [{"id": change, "goal": f"Implement {change}", "covers": [f"element-{change}"], "dependencies": [],
                           "scope": [f"fixture/{change}.txt"], "non_goals": [], "evidence_refs": [], "blocker": None, "ready": True}
                          for change in changes]
    intents_file.write_text(json.dumps(intents), encoding="utf-8")
    for change in changes:
        add_intents.prepare_handoff(ROOT, add_path=add_file, intents_path=intents_file, intent_ids=[change],
                                    out=orch.handoff_dir(directory) / f"{change}.json")
        shutil.copytree(bundles / change, directory / "bundles" / change)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
