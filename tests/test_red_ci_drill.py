"""Temporary red-CI drill: fails only under GitHub Actions, removed before merge."""
import os
import unittest


class RedCiDrill(unittest.TestCase):
    def test_fails_only_in_github_actions(self):
        self.assertIsNone(os.environ.get("GITHUB_ACTIONS"), "deliberate red-CI drill")


if __name__ == "__main__":
    unittest.main()
