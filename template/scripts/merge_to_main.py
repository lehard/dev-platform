from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    print("merge_to_main.py is retained as a compatibility entrypoint; delegating to finish_task.py.")
    return subprocess.run(["python3", str(root / "scripts" / "finish_task.py")], cwd=Path.cwd()).returncode


if __name__ == "__main__":
    raise SystemExit(main())
