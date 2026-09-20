from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import publication_state  # noqa: E402


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=check)


class PublicationStateTestCase(unittest.TestCase):
    """Shared repo + fake-`gh` harness for exercising publication_state directly."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        git("init", "-b", "main", cwd=self.root)
        git("config", "user.name", "Test", cwd=self.root)
        git("config", "user.email", "test@example.invalid", cwd=self.root)
        (self.root / "file.txt").write_text("base\n", encoding="utf-8")
        git("add", ".", cwd=self.root)
        git("commit", "-m", "base", cwd=self.root)
        git("switch", "-c", "agent/task", cwd=self.root)
        (self.root / "file.txt").write_text("feature\n", encoding="utf-8")
        git("commit", "-am", "feature", cwd=self.root)
        self.head = git("rev-parse", "agent/task", cwd=self.root).stdout.strip()
        self.bin = self.base / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_gh(self, body: str) -> dict[str, str]:
        gh = self.bin / "gh"
        gh.write_text(
            "#!/bin/sh\n"
            # Keep older response snippets focused on the stable PR read while
            # adapting their fake transport to the production candidate list.
            "if [ \"$1\" = pr ] && [ \"$2\" = list ] && ! grep -q '^DIRECT_LIST_FIXTURE=1$' \"$0\"; then\n"
            "  payload=$(\"$0\" pr view \"$6\" --json state,headRefOid); rc=$?\n"
            "  if [ $rc -ne 0 ]; then printf '[]'; exit 0; fi\n"
            "  payload=${payload%?}\n"
            "  base=main\n"
            "  auto=null\n"
            "  printf '[%s,\"number\":9,\"url\":\"https://example.invalid/pr/9\",\"baseRefName\":\"%s\",\"headRefName\":\"%s\",\"autoMergeRequest\":%s}]' \"$payload\" \"$base\" \"$6\" \"$auto\"\n"
            "  exit 0\n"
            "fi\n"
            + body
            + "\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(self.bin) + os.pathsep + env["PATH"]
        return env

    def no_pr_gh(self) -> dict[str, str]:
        return self.fake_gh('exit 1\n')


class FindExactHeadPrTests(PublicationStateTestCase):
    def test_exact_local_branch_lookup_uses_registered_branch_head(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"MERGED","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_local_branch_pr(self.root, env, "agent/task", "main")
        self.assertTrue(lookup.available)
        self.assertIsNotNone(lookup.exact_merged)

    def test_exact_local_branch_lookup_fails_closed_when_branch_is_missing(self) -> None:
        lookup = publication_state.find_exact_local_branch_pr(self.root, self.no_pr_gh(), "agent/missing", "main")
        self.assertFalse(lookup.available)
        self.assertIn("unavailable", lookup.detail)

    def test_no_pr_reports_no_match(self) -> None:
        lookup = publication_state.find_exact_head_pr(self.root, self.no_pr_gh(), "agent/task", "main", self.head)
        self.assertTrue(lookup.available)
        self.assertIsNone(lookup.exact_open)
        self.assertIsNone(lookup.exact_merged)
        self.assertIsNone(lookup.stale_open)

    def test_exact_open_pr_is_identified_by_state_and_headRefOid(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$4" = "--json" ] && [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$4" = "--json" ] && [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"autoMergeRequest":null,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNotNone(lookup.exact_open)
        self.assertEqual(lookup.exact_open["number"], 9)
        self.assertEqual(lookup.exact_open["url"], "https://example.invalid/pr/9")
        self.assertIsNone(lookup.exact_merged)
        self.assertIsNone(lookup.stale_open)

    def test_closed_unmerged_pr_with_same_head_is_not_a_match(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"CLOSED","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNone(lookup.exact_open)
        self.assertIsNone(lookup.exact_merged)
        self.assertIsNone(lookup.stale_open)

    def test_merged_pr_with_exact_head_is_identified(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"MERGED","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNotNone(lookup.exact_merged)
        self.assertIsNone(lookup.exact_open)

    def test_reused_branch_selects_current_exact_pr_not_historical_merged_pr(self) -> None:
        old_head = "a" * 40
        env = self.fake_gh(
            'DIRECT_LIST_FIXTURE=1\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  printf \'[{{"number":3,"url":"https://example.invalid/pr/3","state":"MERGED","headRefOid":"{old_head}","baseRefName":"main","headRefName":"agent/task"}},{{"number":4,"url":"https://example.invalid/pr/4","state":"OPEN","headRefOid":"{self.head}","baseRefName":"main","headRefName":"agent/task"}}]\'; exit 0;\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertTrue(lookup.available)
        self.assertEqual(lookup.exact_open["number"], 4)
        self.assertIsNone(lookup.exact_merged)

    def test_open_pr_with_different_head_is_reported_as_stale_not_exact(self) -> None:
        other_head = "0" * 40
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{other_head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNone(lookup.exact_open)
        self.assertIsNone(lookup.exact_merged)
        self.assertIsNotNone(lookup.stale_open)
        self.assertEqual(lookup.stale_open["headRefOid"], other_head)

    def test_open_pr_targeting_a_different_base_is_not_a_match(self) -> None:
        env = self.fake_gh(
            'DIRECT_LIST_FIXTURE=1\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  printf \'[{{"number":9,"url":"https://example.invalid/pr/9","state":"OPEN","headRefOid":"{self.head}","baseRefName":"release/1.0","headRefName":"agent/task"}}]\'; exit 0; fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertIsNone(lookup.exact_open)
        self.assertIsNone(lookup.stale_open)

    def test_unparseable_response_is_reported_unavailable_not_absent(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            '  if [ "$5" = "state,headRefOid" ]; then echo "not json"; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        lookup = publication_state.find_exact_head_pr(self.root, env, "agent/task", "main", self.head)
        self.assertFalse(lookup.available)


class ObservePublicationTests(PublicationStateTestCase):
    def observe(self, env: dict[str, str] | None) -> publication_state.PublicationObservation:
        return publication_state.observe_publication(self.root, self.root, env, "agent/task", "main")

    def test_no_authentication_is_reported_as_github_unavailable(self) -> None:
        obs = self.observe(None)
        self.assertEqual(obs.bucket, publication_state.GITHUB_UNAVAILABLE)
        self.assertFalse(obs.github_available)

    def test_no_pr_yet_is_not_published(self) -> None:
        obs = self.observe(self.no_pr_gh())
        self.assertEqual(obs.bucket, publication_state.NOT_PUBLISHED)

    def test_open_pr_with_pending_checks_and_no_arm_is_open_checks_pending(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main","autoMergeRequest":null}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "[]"; exit 0; fi\n'
            'exit 1'
        )
        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.OPEN_CHECKS_PENDING)
        self.assertFalse(obs.auto_merge_armed)

    def test_open_pr_with_auto_merge_request_is_remote_armed(self) -> None:
        env = self.fake_gh(
            'DIRECT_LIST_FIXTURE=1\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  printf \'[{{"number":9,"url":"https://example.invalid/pr/9","state":"OPEN","headRefOid":"{self.head}","baseRefName":"main","headRefName":"agent/task","autoMergeRequest":{{"enabledBy":"agent"}}}}]\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "[]"; exit 0; fi\n'
            'exit 1'
        )
        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.REMOTE_ARMED)
        self.assertTrue(obs.auto_merge_armed)

    def test_open_pr_with_failed_checks_is_blocked(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo \'[{"name":"ci","state":"FAILURE","workflow":"ci","link":""}]\'; exit 0; fi\n'
            'exit 1'
        )
        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.BLOCKED)

    def test_merged_pr_with_local_main_behind_is_pending_local_reconciliation(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"MERGED","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        # No origin remote configured, so remote_main_head stays None; local main
        # is present -> mismatched (None != a value is False, so this exercises
        # the "cannot confirm reconciled" default of not-pending here). Add a
        # fake remote to make the mismatch concrete instead.
        remote = self.base / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        git("remote", "add", "origin", str(remote), cwd=self.root)
        # Push a *different* main than local, simulating a remote main that has
        # already advanced past what this checkout has fetched/merged locally.
        other = self.base / "other-clone"
        subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
        git("config", "user.name", "Test", cwd=other)
        git("config", "user.email", "test@example.invalid", cwd=other)
        (other / "extra.txt").write_text("extra\n", encoding="utf-8")
        git("add", ".", cwd=other)
        git("commit", "-m", "extra", cwd=other)
        git("push", "origin", "HEAD:main", cwd=other)

        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.REMOTE_MERGED_LOCAL_PENDING)
        self.assertTrue(obs.remote_merged)
        self.assertTrue(obs.local_reconciliation_pending)

    def test_stale_open_pr_for_different_head_reports_detail_without_blocking_new_head(self) -> None:
        other_head = "0" * 40
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{other_head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/9","number":9,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        obs = self.observe(env)
        self.assertEqual(obs.bucket, publication_state.NOT_PUBLISHED)
        self.assertIn(other_head, obs.detail)
        self.assertIn(self.head, obs.detail)


class StatusRenderingTests(PublicationStateTestCase):
    def test_status_payload_never_includes_credential_or_env_fields(self) -> None:
        obs = publication_state.observe_publication(self.root, self.root, None, "agent/task", "main")
        payload = publication_state.status_payload(obs, "unknown")
        blob = json.dumps(payload)
        for forbidden in ("GH_TOKEN", "GITHUB_TOKEN", "password", "Authorization"):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(payload["status"], publication_state.GITHUB_UNAVAILABLE)

    def test_status_text_is_human_readable_and_includes_key_fields(self) -> None:
        obs = publication_state.observe_publication(self.root, self.root, self.no_pr_gh(), "agent/task", "main")
        text = publication_state.status_text(obs, "manual")
        self.assertIn("status: not_published", text)
        self.assertIn("merge_durability: manual", text)


class MergeDurabilityCapabilityTests(PublicationStateTestCase):
    def test_manual_merge_mode_reports_manual_without_any_gh_call(self) -> None:
        result = publication_state.merge_durability_capability({"pr_merge_mode": "manual"}, self.no_pr_gh(), self.root)
        self.assertEqual(result, "manual")

    def test_no_env_reports_unknown(self) -> None:
        result = publication_state.merge_durability_capability({"pr_merge_mode": "auto"}, None, self.root)
        self.assertEqual(result, "unknown")

    def test_auto_merge_allowed_reports_remote_armed_capable(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "repo" ] && [ "$2" = "view" ]; then echo "owner/repo"; exit 0; fi\n'
            'if [ "$1" = "api" ]; then echo "true"; exit 0; fi\n'
            'exit 1'
        )
        result = publication_state.merge_durability_capability({"pr_merge_mode": "auto"}, env, self.root)
        self.assertEqual(result, "remote_armed_capable")

    def test_auto_merge_disallowed_reports_foreground_fallback(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "repo" ] && [ "$2" = "view" ]; then echo "owner/repo"; exit 0; fi\n'
            'if [ "$1" = "api" ]; then echo "false"; exit 0; fi\n'
            'exit 1'
        )
        result = publication_state.merge_durability_capability({"pr_merge_mode": "auto"}, env, self.root)
        self.assertEqual(result, "foreground_fallback")


class RequiredCheckStateForRefTests(PublicationStateTestCase):
    """`required_check_state_for_ref` backs rollout PR adoption: no local checkout exists for
    a rollout branch, so it compares against a caller-supplied expected head instead of a
    local git ref."""

    def test_passed_checks_for_matching_head(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then printf \'{"state":"OPEN","headRefOid":"abc123"}\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then printf \'[{"name":"ci","state":"SUCCESS"}]\'; exit 0; fi\n'
            'exit 1'
        )
        result = publication_state.required_check_state_for_ref(self.root, env, "dev-platform/rollout-v1.0.0", "abc123")
        self.assertEqual(result.kind, "passed")

    def test_failed_checks_for_matching_head(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then printf \'{"state":"OPEN","headRefOid":"abc123"}\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then printf \'[{"name":"ci","state":"FAILURE"}]\'; exit 0; fi\n'
            'exit 1'
        )
        result = publication_state.required_check_state_for_ref(self.root, env, "dev-platform/rollout-v1.0.0", "abc123")
        self.assertEqual(result.kind, "failed")

    def test_changed_head_is_unknown_not_a_silent_pass(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then printf \'{"state":"OPEN","headRefOid":"def456"}\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then printf \'[{"name":"ci","state":"SUCCESS"}]\'; exit 0; fi\n'
            'exit 1'
        )
        result = publication_state.required_check_state_for_ref(self.root, env, "dev-platform/rollout-v1.0.0", "abc123")
        self.assertEqual(result.kind, "unknown")

    def test_unreadable_pr_state_is_unknown(self) -> None:
        result = publication_state.required_check_state_for_ref(self.root, self.no_pr_gh(), "dev-platform/rollout-v1.0.0", "abc123")
        self.assertEqual(result.kind, "unknown")

    def test_pending_checks_for_matching_head(self) -> None:
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then printf \'{"state":"OPEN","headRefOid":"abc123"}\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then printf \'[{"name":"ci","state":"IN_PROGRESS"}]\'; exit 0; fi\n'
            'exit 1'
        )
        result = publication_state.required_check_state_for_ref(self.root, env, "dev-platform/rollout-v1.0.0", "abc123")
        self.assertEqual(result.kind, "pending")


if __name__ == "__main__":
    unittest.main()
