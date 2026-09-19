#!/usr/bin/env python3
"""Inventory bounded evidence and format one project-context question."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


EVIDENCE_PATHS = (
    "README.md",
    "docs/engineering/project-rules.md",
    "dev-platform/checks.toml",
    "openspec/specs",
    "openspec/changes",
    "docs",
)

QUESTIONS = {
    "product": "What product goal, user scenario, or invariant remains unknown after reviewing the repository evidence?",
    "domain": "What domain term or source-of-truth relationship remains ambiguous after reviewing the repository evidence?",
    "architecture": "What durable architecture invariant or prior decision remains unknown after reviewing the repository evidence?",
}


def inventory(root: Path) -> dict[str, object]:
    """List likely sources without inferring facts or writing a draft."""
    evidence = [relative for relative in EVIDENCE_PATHS if (root / relative).exists()]
    context_root = root / "docs" / "context"
    existing_context = (
        sorted(str(path.relative_to(root)) for path in context_root.rglob("*") if path.is_file())
        if context_root.is_dir()
        else []
    )
    return {
        "evidence": evidence,
        "existing_context": existing_context,
        "drafting_rule": "Draft only claims supported by reviewed evidence; leave unresolved facts as TODO or Unknown.",
        "raw_material_policy": "Raw interview/source material is temporary and is never committed automatically.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-first project-context bootstrap helper.")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory_command = commands.add_parser("inventory", help="List bounded evidence before drafting context.")
    inventory_command.add_argument("--json", action="store_true", help="Emit JSON for an agent workflow.")
    question_command = commands.add_parser("question", help="Format one question for a confirmed unresolved concern.")
    question_command.add_argument("concern", choices=sorted(QUESTIONS))
    args = parser.parse_args()

    if args.command == "question":
        print(QUESTIONS[args.concern])
        return 0

    result = inventory(Path.cwd().resolve())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print("Evidence to review before drafting project context:")
    for relative in result["evidence"]:
        print(f"- {relative}")
    if result["existing_context"]:
        print("Existing project-owned context to preserve:")
        for relative in result["existing_context"]:
            print(f"- {relative}")
    print(result["drafting_rule"])
    print(result["raw_material_policy"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
