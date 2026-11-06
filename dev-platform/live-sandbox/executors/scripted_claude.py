#!/usr/bin/env python3
"""Scripted stand-in for the reviewer CLI: answers the readiness probe and returns findings from a control file.

argv: <findings file> <the reviewer CLI arguments>. Reads nothing else, so a run reproduces the same review.
"""
import json
import sys
import uuid
from pathlib import Path


def main() -> int:
    findings_file, arguments = Path(sys.argv[1]), sys.argv[2:]
    result = {"type": "result", "subtype": "success", "is_error": False, "session_id": uuid.uuid4().hex, "result": "ok"}
    if "--json-schema" in arguments:
        result["structured_output"] = {"findings": json.loads(findings_file.read_text(encoding="utf-8"))}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
