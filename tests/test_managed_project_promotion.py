from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "managed_projects.py"
SPEC = importlib.util.spec_from_file_location("managed_projects", MODULE_PATH)
assert SPEC and SPEC.loader
managed_projects = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(managed_projects)


def registry(state: str = "candidate") -> dict:
    return {
        "schema_version": 1,
        "projects": [{
            "repository": "lehard/example",
            "state": state,
            "default_branch": "main",
            "note": "old note",
        }],
    }


class ManagedProjectPromotionTests(unittest.TestCase):
    def test_candidate_promotes_in_place(self) -> None:
        data = registry("candidate")
        changed = managed_projects.promote_repository(data, "lehard/example", "main", "adopted")
        self.assertTrue(changed)
        self.assertEqual(data["projects"][0]["state"], "managed")
        self.assertEqual(data["projects"][0]["note"], "adopted")

    def test_explicit_adoption_can_reclassify_excluded_placeholder(self) -> None:
        data = registry("excluded")
        changed = managed_projects.promote_repository(data, "lehard/example", "main", "activated")
        self.assertTrue(changed)
        self.assertEqual(data["projects"][0]["state"], "managed")

    def test_unknown_repository_is_appended(self) -> None:
        data = {"schema_version": 1, "projects": []}
        managed_projects.promote_repository(data, "lehard/new-project", "trunk", "adopted")
        self.assertEqual(data["projects"][0]["repository"], "lehard/new-project")
        self.assertEqual(data["projects"][0]["default_branch"], "trunk")

    def test_promotion_is_idempotent(self) -> None:
        data = registry("managed")
        data["projects"][0]["note"] = "same"
        changed = managed_projects.promote_repository(data, "lehard/example", "main", "same")
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
