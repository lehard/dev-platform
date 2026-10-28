"""A balanced-parent retained outcome recorded after the coordinator archived the change.

A route-time balanced-parent plan whose developer handoff carried no outcome may record it
after archive, for this task's own change only and with no delegation, plan switch or
execution evidence; every other archived route is still refused.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_model_routing as base  # noqa: E402

routing = base.routing


class BalancedParentRetentionAfterArchiveTests(unittest.TestCase):
    setUp = base.ModelRoutingTests.setUp
    tearDown = base.ModelRoutingTests.tearDown
    record_path = base.ModelRoutingTests.record_path
    durable_record_path = base.ModelRoutingTests.durable_record_path
    prepare_default = base.ModelRoutingTests.prepare_default
    archive_change = base.EarlyRoutingGateTests.archive_change
    archive_gate = base.EarlyRoutingGateTests.archive_gate
    write_content = base.EarlyRoutingGateTests.write_content

    def record_late(self, reason: str = "balanced-parent work completed by the supervisor"):
        with patch.object(routing, "main_root", return_value=self.integration):
            return routing.record_retained_execution(self.task, reason=reason)

    def edit_plan(self, **changes) -> None:
        payload = json.loads(self.record_path().read_text(encoding="utf-8"))
        payload["execution_plan"].update(changes)
        self.record_path().write_text(json.dumps(payload), encoding="utf-8")

    def test_balanced_parent_outcome_is_recorded_after_archive(self) -> None:
        route = self.prepare_default("standard")
        self.assertEqual(route.execution_plan["policy"], routing.BALANCED_PARENT_POLICY)
        self.write_content()
        self.archive_change()
        with self.assertRaisesRegex(routing.RoutingError, "no completed execution outcome"):
            self.archive_gate()
        execution = self.record_late()
        self.assertEqual((execution["outcome"], execution["retained"]["policy"]), ("retained", routing.BALANCED_PARENT_POLICY))
        self.assertNotIn("owner_approval", execution["retained"])
        self.assertEqual(self.archive_gate().execution["outcome"], "retained")
        with self.assertRaisesRegex(routing.RoutingError, "is archived"):
            self.record_late("duplicate")

    def test_switched_balanced_parent_is_still_refused(self) -> None:
        self.prepare_default("standard")
        self.write_content()
        self.archive_change()
        self.edit_plan(switched_from={"mode": routing.PLAN_DELEGATED})
        before = self.record_path().read_text(encoding="utf-8")
        with self.assertRaisesRegex(routing.RoutingError, "is archived: only an owner-approved"):
            self.record_late("late retention")
        self.assertEqual(self.record_path().read_text(encoding="utf-8"), before)
        self.assertFalse(self.durable_record_path().exists())

    def test_other_archived_routes_are_still_refused(self) -> None:
        for label, profile, delegate in (("delegated-child", "standard", True), ("complex-parent", "complex", False)):
            with self.subTest(label):
                self.tearDown()
                self.setUp()
                self.prepare_default(profile, delegate=delegate)
                self.write_content()
                self.archive_change()
                with self.assertRaisesRegex(routing.RoutingError, "is archived: only an owner-approved"):
                    self.record_late("late retention")
                self.assertFalse(self.durable_record_path().exists())


if __name__ == "__main__":
    unittest.main()
