"""The one test group of the sandbox: a composition runs the platform full set over the fixture."""
import unittest
from pathlib import Path


class FixtureTest(unittest.TestCase):
    def test_the_required_check_exists(self):
        self.assertTrue((Path(__file__).resolve().parents[1] / "fixture" / "check.py").is_file())


if __name__ == "__main__":
    unittest.main()
