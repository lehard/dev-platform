"""The sandbox required check: a scenario turns it red by writing `red` into verdict.txt."""
from pathlib import Path
import sys

verdict = (Path(__file__).parent / "verdict.txt").read_text(encoding="utf-8").strip()
if verdict != "green":
    sys.exit(f"fixture verdict is {verdict!r}")
