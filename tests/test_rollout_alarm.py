from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_alarm as ra  # noqa: E402
import rollout_failure_streak as rfs  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "rollout.yml"
REPO = "lehard/dev-platform"


def job(job_id: int, name: str, conclusion: str | None, failed_step: str | None = None) -> dict:
    steps = [{"name": "Checkout platform", "conclusion": "success"}]
    if failed_step:
        steps.append({"name": failed_step, "conclusion": "failure"})
    return {"id": job_id, "name": name, "conclusion": conclusion, "steps": steps,
            "html_url": f"https://github.com/{REPO}/actions/runs/1/job/{job_id}"}


def lines(items: list[dict]) -> str:
    return "".join(json.dumps(item) + "\n" for item in items)


class FakeGh:
    """Answers the GitHub reads of one run and records every write."""

    def __init__(self, jobs: list[dict], annotations: dict[int, list[dict]], open_issues: list[dict] | None = None,
                 fail_on: str | None = None) -> None:
        self.jobs = jobs
        self.annotations = annotations
        self.open_issues = open_issues or []
        self.fail_on = fail_on
        self.writes: list[list[str]] = []

    def __call__(self, args: list[str]) -> str:
        if self.fail_on and self.fail_on in " ".join(args[:3]):
            raise ra.AlarmError(f"gh {' '.join(args[:2])} failed: HTTP 403")
        if args[:2] == ["api", "--paginate"] and args[2].endswith("/jobs"):
            return lines(self.jobs)
        if args[:2] == ["api", "--paginate"] and args[2].endswith("/annotations"):
            return lines(self.annotations.get(int(args[2].split("/")[-2]), []))
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.open_issues)
        self.writes.append(args)
        if args[:2] == ["issue", "create"]:
            return f"https://github.com/{REPO}/issues/901\n"
        return ""


def report_args(summary: Path, **overrides: str) -> argparse.Namespace:
    values = {
        "repository": REPO, "run_id": "40469918454", "run_attempt": "1",
        "server_url": "https://github.com", "event": "workflow_dispatch", "actor": "github-actions[bot]",
        "alarm_job": "alarm", "planned_version": "", "requested_version": "v2.0.0",
        "requested_repository": "", "version_file": summary.parent / "VERSION", "summary_output": summary,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


# Shape of the real v2.0.0 run 40469918454: plan failed, matrix never expanded.
PLAN_FAILED = [
    job(122074285072, "plan", "failure", "Checkout operator registry"),
    job(122074503723, "${{ matrix.repository }} -> ${{ needs.plan.outputs.version }}", "skipped"),
    job(3, "alarm", None),
]
PLAN_ANNOTATIONS = {122074285072: [
    {"annotation_level": "failure", "message": "The process '/usr/bin/git' failed with exit code 128"},
    {"annotation_level": "failure", "message": "repository 'https://github.com/lehard/dev-platform-operator/' not found"},
    {"annotation_level": "failure", "message": "repository 'https://github.com/lehard/dev-platform-operator/' not found"},
    {"annotation_level": "notice", "message": "ubuntu-latest label migration"},
]}


class RolloutAlarmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.summary = Path(self.tmp.name) / "summary.md"
        (Path(self.tmp.name) / "VERSION").write_text("2.0.0\n", encoding="utf-8")

    def run_report(self, gh: FakeGh, **overrides: str) -> int:
        with patch.object(ra, "run_gh", side_effect=gh), patch.object(rfs, "run_gh") as label_gh:
            result = ra.cmd_report(report_args(self.summary, **overrides))
        self.label_calls = label_gh.call_args_list
        return result

    def test_plan_failure_opens_release_alarm_with_stage_step_and_error(self) -> None:
        gh = FakeGh(PLAN_FAILED, PLAN_ANNOTATIONS)
        self.assertEqual(self.run_report(gh), 0)
        self.assertEqual(len(gh.writes), 1)
        create = gh.writes[0]
        self.assertEqual(create[:2], ["issue", "create"])
        self.assertIn("Managed rollout failed: v2.0.0", create)
        self.assertEqual(create[create.index("--label") + 1], rfs.ALERT_LABEL)
        body = create[create.index("--body") + 1]
        self.assertIn("| `plan` | Checkout operator registry |", body)
        self.assertIn("repository 'https://github.com/lehard/dev-platform-operator/' not found", body)
        self.assertEqual(body.count("dev-platform-operator/' not found"), 1)
        self.assertNotIn("ubuntu-latest", body)
        self.assertNotIn("matrix.repository", body)
        self.assertIn("triggered by `github-actions[bot]`", body)
        self.assertIn("all managed projects", body)
        self.assertEqual(self.label_calls[0].args[0][:3], ["label", "create", rfs.ALERT_LABEL])
        self.assertIn("issues/901", self.summary.read_text(encoding="utf-8"))

    def test_plan_failure_before_version_resolution_names_release_from_version_file(self) -> None:
        gh = FakeGh(PLAN_FAILED, PLAN_ANNOTATIONS)
        self.assertEqual(self.run_report(gh, requested_version="", actor="lehard",
                                         requested_repository="lehard/terrazzo_mvp"), 0)
        create = gh.writes[0]
        self.assertIn("Managed rollout failed: v2.0.0", create)
        body = create[create.index("--body") + 1]
        self.assertIn("triggered by `lehard`", body)
        self.assertIn("`lehard/terrazzo_mvp`", body)

    def test_partial_failure_lists_only_failed_targets(self) -> None:
        jobs = [
            job(1, "plan", "success"),
            job(2, "lehard/terrazzo_mvp -> v2.0.0", "success"),
            job(3, "kamenkadmitry/ai_assist_content -> v2.0.0", "failure", "Create write-capable target token"),
            job(4, "lehard/Jara_Fin -> v2.0.0", "cancelled"),
            job(5, "alarm", None),
        ]
        annotations = {3: [{"annotation_level": "failure", "message": "Failed to create token: Not Found"}]}
        gh = FakeGh(jobs, annotations)
        self.assertEqual(self.run_report(gh, planned_version="v2.0.0"), 0)
        body = gh.writes[0][gh.writes[0].index("--body") + 1]
        self.assertIn("| `kamenkadmitry/ai_assist_content` | Create write-capable target token | Failed to create token: Not Found |", body)
        self.assertIn("`lehard/Jara_Fin` | no failed step recorded (job cancelled)", body)
        self.assertIn("no error annotation was recorded; see the job log https://github.com/lehard/dev-platform/actions/runs/1/job/4", body)
        self.assertNotIn("terrazzo_mvp", body)

    def test_skipped_target_after_successful_plan_is_a_failure(self) -> None:
        jobs = [job(1, "plan", "success"), job(2, "lehard/terrazzo_mvp -> v2.0.0", "skipped"), job(5, "alarm", None)]
        gh = FakeGh(jobs, {})
        self.assertEqual(self.run_report(gh, planned_version="v2.0.0"), 0)
        self.assertEqual(gh.writes[0][:2], ["issue", "create"])

    def test_later_failing_run_comments_on_the_open_alarm(self) -> None:
        gh = FakeGh(PLAN_FAILED, PLAN_ANNOTATIONS, open_issues=[
            {"number": 77, "title": "Managed rollout repeatedly failing: lehard/x"},
            {"number": 900, "title": "Managed rollout failed: v2.0.0"},
        ])
        self.assertEqual(self.run_report(gh), 0)
        self.assertEqual(len(gh.writes), 1)
        self.assertEqual(gh.writes[0][:3], ["issue", "comment", "900"])

    def test_successful_run_raises_no_alarm(self) -> None:
        jobs = [job(1, "plan", "success"), job(2, "lehard/terrazzo_mvp -> v2.0.0", "success"), job(5, "alarm", None)]
        gh = FakeGh(jobs, {})
        self.assertEqual(self.run_report(gh, planned_version="v2.0.0"), 0)
        self.assertEqual(gh.writes, [])
        self.assertEqual(self.label_calls, [])
        self.assertFalse(self.summary.exists())

    def test_successful_run_notes_but_keeps_open_alarm(self) -> None:
        jobs = [job(1, "plan", "success"), job(2, "lehard/terrazzo_mvp -> v2.0.0", "success"), job(5, "alarm", None)]
        gh = FakeGh(jobs, {}, open_issues=[{"number": 900, "title": "Managed rollout failed: v2.0.0"}])
        self.assertEqual(self.run_report(gh, planned_version="v2.0.0", requested_repository="lehard/terrazzo_mvp"), 0)
        self.assertEqual(len(gh.writes), 1)
        self.assertEqual(gh.writes[0][:3], ["issue", "comment", "900"])
        self.assertIn("`lehard/terrazzo_mvp`", gh.writes[0][-1])
        self.assertNotIn("close", [part for write in gh.writes for part in write])

    def test_delivery_failure_fails_the_alarm(self) -> None:
        gh = FakeGh(PLAN_FAILED, PLAN_ANNOTATIONS, fail_on="issue create")
        with self.assertRaisesRegex(ra.AlarmError, "gh issue create failed: HTTP 403"):
            self.run_report(gh)

    def test_unreadable_run_fails_the_alarm(self) -> None:
        gh = FakeGh(PLAN_FAILED, PLAN_ANNOTATIONS, fail_on="api --paginate repos/lehard/dev-platform/actions")
        with self.assertRaisesRegex(ra.AlarmError, "gh api --paginate failed"):
            self.run_report(gh)

    def test_label_bootstrap_failure_propagates(self) -> None:
        gh = FakeGh(PLAN_FAILED, PLAN_ANNOTATIONS)
        with patch.object(ra, "run_gh", side_effect=gh), \
             patch.object(rfs, "run_gh", side_effect=rfs.TrackerError("gh label create failed: HTTP 403")):
            with self.assertRaisesRegex(rfs.TrackerError, "label create"):
                ra.cmd_report(report_args(self.summary))
        self.assertEqual(gh.writes, [])

    def test_main_exits_non_zero_naming_the_failure(self) -> None:
        argv = ["rollout_alarm.py", "--repository", REPO, "--run-id", "1", "--run-attempt", "1",
                "--server-url", "https://github.com", "--event", "workflow_dispatch", "--actor", "lehard",
                "--alarm-job", "alarm", "--planned-version", "", "--requested-version", "v2.0.0",
                "--requested-repository", "", "--version-file", str(Path(self.tmp.name) / "VERSION")]
        with patch.object(sys, "argv", argv), \
             patch.object(ra, "run_gh", side_effect=ra.AlarmError("gh api --paginate failed: HTTP 404")), \
             patch("sys.stderr") as stderr:
            self.assertEqual(ra.main(), 1)
        written = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertIn("Managed rollout alarm not delivered", written)
        self.assertIn("HTTP 404", written)

    def test_run_without_plan_job_is_refused(self) -> None:
        gh = FakeGh([job(5, "alarm", None)], {})
        with self.assertRaisesRegex(ra.AlarmError, "exactly one 'plan' job"):
            self.run_report(gh)


class RolloutAlarmWorkflowTests(unittest.TestCase):
    def alarm_job(self) -> str:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("\n  alarm:\n", text)
        return text.split("\n  alarm:\n", 1)[1]

    def test_alarm_job_always_runs_after_plan_and_rollout(self) -> None:
        block = self.alarm_job()
        self.assertIn("needs: [plan, rollout]", block)
        self.assertIn("if: always()", block)
        self.assertNotIn("continue-on-error", block)

    def test_alarm_job_uses_workflow_ref_code_and_least_privilege_token(self) -> None:
        block = self.alarm_job()
        self.assertIn("python3 scripts/rollout_alarm.py", block)
        self.assertNotIn("platform/scripts", block)
        self.assertNotIn("ref:", block)
        for permission in ("actions: read", "checks: read", "contents: read", "issues: write"):
            self.assertIn(permission, block)
        self.assertIn("GH_TOKEN: ${{ github.token }}", block)
        self.assertNotIn("create-github-app-token", block)

    def test_alarm_job_passes_both_dispatch_paths_context(self) -> None:
        block = self.alarm_job()
        for fragment in (
            "--alarm-job alarm",
            "${{ needs.plan.outputs.version }}",
            "${{ inputs.version }}",
            "${{ inputs.repository }}",
            '--event "$GITHUB_EVENT_NAME"',
            '--actor "$GITHUB_TRIGGERING_ACTOR"',
            '--run-attempt "$GITHUB_RUN_ATTEMPT"',
            "--version-file VERSION",
        ):
            self.assertIn(fragment, block)

    def test_release_workflow_still_dispatches_the_same_rollout_workflow(self) -> None:
        text = (ROOT / ".github" / "workflows" / "publish-version.yml").read_text(encoding="utf-8")
        self.assertIn('gh workflow run rollout.yml --repo "$GITHUB_REPOSITORY" --ref main -f "version=$TAG"', text)


if __name__ == "__main__":
    unittest.main()
