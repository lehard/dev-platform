from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


start_tier_routing = load("start_tier_routing", "start_tier_routing.py")


class StartTierRoutingTests(unittest.TestCase):
    def test_default_recommendation_is_r2_with_no_trigger(self) -> None:
        receipt = start_tier_routing.recommend_start_tier(strong_trigger=None)
        self.assertEqual(receipt["recommended_start_tier"], "R2")
        self.assertIsNone(receipt["strong_trigger"])
        self.assertEqual(receipt["rubric_version"], start_tier_routing.RUBRIC_VERSION)
        self.assertEqual(receipt["effort_hint"], "medium")

    def test_valid_hard_trigger_recommends_r3(self) -> None:
        receipt = start_tier_routing.recommend_start_tier(strong_trigger="unresolved_architecture")
        self.assertEqual(receipt["recommended_start_tier"], "R3")
        self.assertEqual(receipt["strong_trigger"], "unresolved_architecture")
        self.assertEqual(receipt["effort_hint"], "high")

    def test_unsupported_trigger_is_rejected(self) -> None:
        with self.assertRaisesRegex(start_tier_routing.StartTierError, "unsupported frontier hard trigger"):
            start_tier_routing.recommend_start_tier(strong_trigger="big diff")

    def test_diff_size_style_reasoning_is_not_a_supported_trigger(self) -> None:
        # The rubric intentionally has no "blast radius" or "many files"
        # trigger category -- those may raise assurance while staying R2.
        for fake_trigger in ("blast_radius", "many_files", "high_visibility", "large_diff"):
            with self.assertRaises(start_tier_routing.StartTierError):
                start_tier_routing.recommend_start_tier(strong_trigger=fake_trigger)

    def test_high_assurance_is_independent_of_tier(self) -> None:
        receipt = start_tier_routing.recommend_start_tier(strong_trigger=None, assurance="high")
        self.assertEqual(receipt["recommended_start_tier"], "R2")
        self.assertEqual(receipt["assurance"], "high")

    def test_title_prefix_matches_tier(self) -> None:
        self.assertEqual(start_tier_routing.title_prefix("R2"), "[R2]")
        self.assertEqual(start_tier_routing.title_prefix("R3"), "[R3]")
        with self.assertRaises(start_tier_routing.StartTierError):
            start_tier_routing.title_prefix("R9")

    def test_tier_to_profile_mapping(self) -> None:
        self.assertEqual(start_tier_routing.tier_to_profile("R2"), "standard")
        self.assertEqual(start_tier_routing.tier_to_profile("R3"), "complex")

    def test_r1_is_reserved_and_disabled_for_execution_mapping(self) -> None:
        with self.assertRaisesRegex(start_tier_routing.StartTierError, "reserved and disabled"):
            start_tier_routing.tier_to_profile("R1")

    def test_validate_routing_receipt_accepts_a_well_formed_r2_receipt(self) -> None:
        receipt = start_tier_routing.recommend_start_tier(strong_trigger=None)
        self.assertEqual(start_tier_routing.validate_routing_receipt(receipt), receipt)

    def test_validate_routing_receipt_accepts_absence(self) -> None:
        self.assertIsNone(start_tier_routing.validate_routing_receipt(None))

    def test_validate_routing_receipt_rejects_r3_without_a_trigger(self) -> None:
        forged = start_tier_routing.recommend_start_tier(strong_trigger=None)
        forged["recommended_start_tier"] = "R3"
        with self.assertRaisesRegex(start_tier_routing.StartTierError, "concrete supported hard-trigger"):
            start_tier_routing.validate_routing_receipt(forged)

    def test_validate_routing_receipt_rejects_r1(self) -> None:
        forged = start_tier_routing.recommend_start_tier(strong_trigger=None)
        forged["recommended_start_tier"] = "R1"
        with self.assertRaisesRegex(start_tier_routing.StartTierError, "reserved and disabled"):
            start_tier_routing.validate_routing_receipt(forged)

    def test_validate_routing_receipt_rejects_wrong_shape(self) -> None:
        with self.assertRaises(start_tier_routing.StartTierError):
            start_tier_routing.validate_routing_receipt({"recommended_start_tier": "R2"})


if __name__ == "__main__":
    unittest.main()
