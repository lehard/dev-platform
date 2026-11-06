"""The sandbox required check. A scenario turns it red by writing `red` into verdict.txt, or red on CI only through ci-verdict.txt."""
from pathlib import Path
import os
import sys

fixture = Path(__file__).parent
files = ["verdict.txt", "ci-verdict.txt"] if os.environ.get("GITHUB_ACTIONS") == "true" else ["verdict.txt"]
for name in files:
    verdict = (fixture / name).read_text(encoding="utf-8").strip()
    if verdict != "green":
        sys.exit(f"fixture {name} is {verdict!r}")
