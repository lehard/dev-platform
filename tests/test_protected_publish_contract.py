from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProtectedPublishContractTests(unittest.TestCase):
    def test_project_publish_refuses_declared_protected_main_in_direct_mode(self) -> None:
        text = (ROOT / "template" / "scripts" / "project_publish.py").read_text(encoding="utf-8")
        self.assertIn("protected_main(config)", text)
        self.assertIn("protected_main=true is incompatible with direct publication", text)
        self.assertLess(text.index("protected_main(config)"), text.index("return publish_direct(root, args.remote, main_branch)"))


if __name__ == "__main__":
    unittest.main()
