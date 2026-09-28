from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import code_erosion_report as report  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "code-erosion.yml"
HUMAN = """erosion: function `big` exceeds complexity threshold
    ┌─ scripts/a.py:10
    │
 10 │ def big():
    │
    = complexity: 30, sloc: 80 (threshold: complexity > 10)

erosion: function `mid` exceeds complexity threshold
    ┌─ scripts/b.py:3
    │
    = complexity: 12, sloc: 20 (threshold: complexity > 10)
"""
DATA = {"verbosity": 0.1, "erosion": 0.5, "cog_erosion": 0.6, "files_scanned": 2,
        "total_loc": 100, "high_cc_functions": 2, "total_functions": 9}


class CodeErosionTests(unittest.TestCase):
    def area(self, tmp: str, data: object | None, exit_code: str = "1") -> str:
        base = Path(tmp) / "a"
        if data is not None:
            base.with_suffix(".json").write_text(data if isinstance(data, str) else json.dumps(data))
        base.with_suffix(".txt").write_text(HUMAN)
        base.with_suffix(".exit").write_text(exit_code)
        return str(base)

    def test_version_is_exact_pin(self) -> None:
        version = (ROOT / ".github/code-erosion/scb-check-version.txt").read_text().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        text = WORKFLOW.read_text()
        self.assertIn("scb-check==${version}", text)
        froms = re.findall(r"uvx --from (\S+)", text)
        self.assertTrue(froms)
        self.assertTrue(all(f == '"scb-check==${version}"' for f in froms), froms)
        for use in re.findall(r"uses: (\S+)", text):
            self.assertRegex(use, r"@[0-9a-f]{40}$", use)

    def test_workflow_is_non_blocking(self) -> None:
        wf = yaml.safe_load(WORKFLOW.read_text())
        job = wf["jobs"]["erosion"]
        self.assertTrue(job["continue-on-error"])
        self.assertEqual(wf["permissions"], {"contents": "read", "pull-requests": "write"})
        runs = "\n".join(s.get("run", "") for s in job["steps"])
        self.assertIn("set +e", runs)
        self.assertNotIn("exit 1", runs)

    def test_renders_metrics_and_top_hotspots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = report.render("0.2.0", [("scripts", self.area(tmp, DATA))])
        self.assertTrue(out.startswith(report.MARKER))
        self.assertIn("0.500", out)
        self.assertLess(out.index("`big`"), out.index("`mid`"))
        self.assertIn("not a quality score", out)

    def test_degrades_on_garbled_or_missing_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for data in ("not json", None, {"verbosity": 1}):
                out = report.render("0.2.0", [("scripts", self.area(tmp, data))])
                self.assertIn(report.MARKER, out)
                self.assertIn("no usable report", out)

    def test_cli_always_exits_zero(self) -> None:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/code_erosion_report.py"), "--version", "0.2.0",
                               "--area", "x=/nonexistent/none"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn(report.MARKER, proc.stdout)


if __name__ == "__main__":
    unittest.main()
