#!/usr/bin/env python3
"""Dogfood the generated managed-task importer from this source repository."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "template" / "scripts" / "managed_task.py"
sys.path.insert(0, str(SCRIPT.parent))
runpy.run_path(str(SCRIPT), run_name="__main__")
