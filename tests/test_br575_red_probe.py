"""Temporary BR-575 ruleset probe: intentionally failing; this PR must never merge."""
import unittest


class RedProbe(unittest.TestCase):
    def test_intentionally_red(self):
        self.fail("BR-575 ruleset probe: validate must be red")


if __name__ == "__main__":
    unittest.main()
