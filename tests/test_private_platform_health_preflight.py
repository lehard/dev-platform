from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import private_platform_health_preflight as preflight  # noqa: E402


class PrivatePlatformHealthPreflightTests(unittest.TestCase):
    def test_missing_token_is_degraded_without_running_gh(self) -> None:
        with patch.object(preflight, "_api") as api:
            result = preflight.preflight(token="", platform_repository="owner/platform", backlog_repository="owner/backlog")
        self.assertEqual(result.status, "degraded")
        self.assertEqual(result.unavailable_evidence, preflight.UNAVAILABLE_CATEGORY)
        api.assert_not_called()

    def test_all_bounded_read_probes_must_succeed(self) -> None:
        with patch.object(preflight, "_api", return_value=True) as api:
            result = preflight.preflight(token="token", platform_repository="owner/platform", backlog_repository="owner/backlog")
        self.assertEqual(result.status, "available")
        self.assertEqual(api.call_count, 4)
        self.assertEqual(api.call_args_list[0].args[1], "repos/owner/platform/contents/openspec/specs/platform-health-review/spec.md")
        self.assertEqual(api.call_args_list[-1].args[1], "repos/owner/backlog/pulls?state=closed&per_page=1")

    def test_any_failed_probe_is_degraded(self) -> None:
        with patch.object(preflight, "_api", side_effect=[True, True, False]) as api:
            result = preflight.preflight(token="token", platform_repository="owner/platform", backlog_repository="owner/backlog")
        self.assertEqual(result.status, "degraded")
        self.assertEqual(api.call_count, 3)

    def test_output_contains_status_and_no_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"
            preflight.write_output(str(output), preflight.PreflightResult("degraded", "private access"))
            text = output.read_text(encoding="utf-8")
        self.assertIn("private_evidence_status=degraded", text)
        self.assertIn("unavailable_evidence=private access", text)
        self.assertNotIn("token", text)
