"""Run a self-contained generated lifecycle primitive from the source checkout.

The central repository is deliberately not rendered from its own Copier
template.  These adapters keep that difference explicit while executing the
same authoritative lifecycle and publication modules that are released to
managed projects.  Downstream projects never import this module.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPTS = ROOT / "template" / "scripts"


def run_template(name: str) -> None:
    target = TEMPLATE_SCRIPTS / name
    if not target.is_file():
        raise SystemExit(f"Central lifecycle primitive is missing: {target}")
    sys.path.insert(0, str(TEMPLATE_SCRIPTS))
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")
