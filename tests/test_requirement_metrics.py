from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import requirement_metrics as metrics  # noqa: E402

REQUIREMENT = "acme/backlog#7"
CHILD = "acme/backlog#8"
CHANGE = "alpha-change"
TARGET = "acme/project"
ARCHIVE = f"openspec/changes/archive/2026-01-02-{CHANGE}"
ACTIVE = f"openspec/changes/{CHANGE}"
# Synthetic prose that must never leave the sources.
SECRETS = (
    "SECRET-FINDING-SUMMARY", "SECRET-FINDING-EVIDENCE", "SECRET-DISPOSITION-RATIONALE", "SECRET-FRICTION-OBSERVATION",
    "SECRET-ESCALATION-REASON", "SECRET-ROUTING-RATIONALE", "SECRET-PROMPT-TEXT", "SECRET-TOOL-INPUT",
    "SECRET-TOOL-OUTPUT", "SECRET-LIMITATION", "SECRET-ADD-QUESTION",
)


def review_report(perspective: str, request: str, digest: str | None, *, launched: str, completed: str,
                  available: bool = True, material: int = 0, limitation: str = "timed out") -> dict:
    report = {
        "schema_version": 1, "perspective": perspective, "request_id": request, "task_content_digest": digest,
        "candidate": {"base_ref": "origin/main"}, "launched_at": launched, "completed_at": completed,
        "reviewer": {"runtime": "claude-code-print", "provider": "claude", "launch_id": f"{request}-{perspective}",
                     "context_id": "ctx", "fresh_context": True, "write_access": False,
                     "launch_evidence": "platform-observed", "model": {"value": "sonnet", "source": "selected"}},
    }
    if available:
        report.update(availability="available", findings=[
            {"id": f"f{index}", "severity": "material", "summary": "SECRET-FINDING-SUMMARY", "evidence": "SECRET-FINDING-EVIDENCE"}
            for index in range(material)
        ] + [{"id": "note", "severity": "advisory", "summary": "SECRET-FINDING-SUMMARY", "evidence": "x"}])
    else:
        report.update(availability="unavailable", findings=[], limitation=f"claude reviewer {limitation} SECRET-LIMITATION")
    return report


def checks(duration: float, *, full: bool) -> dict:
    commands = [{"command": "python3 -m compileall -q template/scripts scripts", "duration_seconds": duration, "outcome": "success", "exit_code": 0}]
    if full:
        commands.append({"command": "python3 scripts/run_test_groups.py --all", "duration_seconds": 100.0, "outcome": "success", "exit_code": 0})
    return {"version": 2, "outcome": "success", "executed_commands": commands}


def pair(request: str, digest: str | None, launched: str, completed: str, **kwargs: object) -> dict[str, dict]:
    return {
        "spec-fidelity": review_report("spec-fidelity", request, digest, launched=launched, completed=completed,
                                       material=int(kwargs.get("material", 0))),
        "engineering-quality": review_report("engineering-quality", request, digest, launched=launched, completed=completed,
                                             available=bool(kwargs.get("available", True))),
    }


ROUND1 = pair("r1", "D1", "2026-01-02T09:50:00Z", "2026-01-02T09:55:00Z", material=1)
ROUND2 = pair("r2", "D2", "2026-01-02T10:20:00Z", "2026-01-02T10:25:00Z", available=False)
ROUND3 = pair("r3", "D2", "2026-01-02T10:50:00Z", "2026-01-02T10:58:00Z", material=1)
DISPOSITIONS = {"schema_version": 1, "dispositions": [
    {"perspective": "spec-fidelity", "finding": "f0", "status": "rejected", "rationale": "SECRET-DISPOSITION-RATIONALE"},
]}


def dumps(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def commit_files(prefix: str, *, reports: dict[str, dict] | None = None, automated: dict | None = None,
                 dispositions: dict | None = None) -> dict[str, str]:
    files: dict[str, str] = {}
    for perspective, report in (reports or {}).items():
        files[f"{prefix}/independent-reviews/{perspective}.json"] = dumps(report)
    if automated is not None:
        files[f"{prefix}/automated-checks.json"] = dumps(automated)
    if dispositions is not None:
        files[f"{prefix}/independent-review-dispositions.json"] = dumps(dispositions)
    return files


COMMITS = [
    ("c1", "2026-01-02T09:40:00Z", commit_files(ACTIVE, automated=checks(1.0, full=False))),
    ("c2", "2026-01-02T10:00:00Z", commit_files(ACTIVE, reports=ROUND1)),
    ("c3", "2026-01-02T10:30:00Z", commit_files(ACTIVE, reports=ROUND2, automated=checks(2.0, full=False))),
    ("c4", "2026-01-02T11:00:00Z", commit_files(ACTIVE, reports=ROUND3)),
    ("c5", "2026-01-02T11:30:00Z", commit_files(ARCHIVE, reports=ROUND3, automated=checks(3.0, full=True), dispositions=DISPOSITIONS)),
]


def run(run_id: int, name: str, head: str, started: str, updated: str, conclusion: str = "success", attempt: int = 1) -> dict:
    return {"id": run_id, "name": name, "head_sha": head, "status": "completed", "conclusion": conclusion,
            "run_attempt": attempt, "run_started_at": started, "updated_at": updated}


class FakeGitHub:
    """Serve synthetic GitHub REST responses; any unknown path is a remote failure."""

    def __init__(self, *, fail: tuple[str, ...] = ()) -> None:
        self.fail = fail
        self.calls: list[list[str]] = []
        self.responses: dict[str, object] = {
            f"repos/acme/backlog/issues/7": {
                "number": 7, "title": "Improve delivery", "state": "closed", "created_at": "2026-01-02T08:00:00Z",
                "closed_at": "2026-01-02T12:00:00Z", "labels": [{"name": "type:requirement"}],
                "body": "## Outcome\n\nx\n\n<!-- requirement-children:start -->\n- [x] acme/backlog#8\n<!-- requirement-children:end -->\n",
            },
            f"repos/acme/backlog/issues/8": {
                "number": 8, "state": "closed", "created_at": "2026-01-02T09:00:00Z", "closed_at": "2026-01-02T11:50:00Z",
                "labels": [{"name": "type:internal-change"}],
                "body": f"**Target repository:** `{TARGET}`\n\n**OpenSpec change:** `{CHANGE}`\n\nRequirement: {REQUIREMENT}\n",
            },
            f"repos/{TARGET}/pulls?state=all&head=acme:agent/{CHANGE}": [
                {"number": 31, "state": "closed", "created_at": "2026-01-02T11:32:00Z", "merged_at": "2026-01-02T11:45:00Z",
                 "head": {"sha": "c5"}},
            ],
            f"repos/{TARGET}/pulls/31/commits": [
                {"sha": sha, "commit": {"committer": {"date": date}}} for sha, date, _ in COMMITS
            ],
            f"repos/{TARGET}/issues/31/events": [
                {"event": "labeled", "label": {"name": "publication:queued"}},
                {"event": "labeled", "label": {"name": "publication:blocked"}},
                {"event": "labeled", "label": {"name": "publication:queued"}},
                {"event": "merged", "label": None},
            ],
            f"repos/{TARGET}/actions/runs?branch=agent%2F{CHANGE}": {"workflow_runs": [
                run(1, "Platform CI", "c1", "2026-01-02T09:45:00Z", "2026-01-02T09:50:00Z"),
                run(2, "Platform CI", "c3", "2026-01-02T10:35:00Z", "2026-01-02T10:40:00Z"),
                run(3, "Platform CI", "c4", "2026-01-02T11:05:00Z", "2026-01-02T11:10:00Z", conclusion="failure", attempt=2),
                run(4, "Platform CI", "c5", "2026-01-02T11:35:00Z", "2026-01-02T11:40:00Z"),
                run(5, "Code Erosion", "c5", "2026-01-02T11:35:00Z", "2026-01-02T11:36:00Z"),
            ]},
        }
        for sha, _, files in COMMITS:
            self.responses[f"repos/{TARGET}/commits/{sha}"] = {
                "files": [{"filename": path, "status": "added"} for path in files] + [{"filename": "src/app.py", "status": "modified"}],
            }
            for path, content in files.items():
                self.responses[f"raw:repos/{TARGET}/contents/{path}?ref={sha}"] = content

    def __call__(self, args: list[str]) -> str:
        self.calls.append(list(args))
        path = args[-1]
        raw = "-H" in args
        base, _, query = path.partition("?")
        params = [part for part in query.split("&") if part and not part.startswith(("per_page=", "page="))]
        page = next((int(part[5:]) for part in query.split("&") if part.startswith("page=")), 1)
        key = base + ("?" + "&".join(params) if params else "")
        if any(marker in key for marker in self.fail):
            raise metrics.GitHubUnavailable(f"simulated failure for {base}")
        if raw:
            return str(self.responses[f"raw:{key}"])
        if key not in self.responses:
            raise metrics.GitHubUnavailable(f"no fake response for {key}")
        value = self.responses[key]
        if page > 1:
            value = {"workflow_runs": []} if isinstance(value, dict) and "workflow_runs" in value else []
        return json.dumps(value)


def transcript_entry(kind: str, at: str, *, session: str = "s1", branch: str = "main", content: object = None,
                     **extra: object) -> dict:
    entry = {"type": kind, "timestamp": at, "sessionId": session, "gitBranch": branch, "cwd": "/x",
             "message": {"role": kind, "content": content if content is not None else "hi"}}
    entry.update(extra)
    return entry


def assistant(at: str, request: str, *, branch: str = "main", tool_input: dict | None = None, session: str = "s1") -> dict:
    content = [{"type": "tool_use", "id": "t", "name": "Bash", "input": tool_input or {"command": "SECRET-TOOL-INPUT"}}]
    entry = transcript_entry("assistant", at, branch=branch, content=content, session=session, requestId=request)
    entry["message"]["usage"] = {"input_tokens": 10, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 5, "output_tokens": 7}
    return entry


class RequirementMetricsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.root = base / "repo"
        self.projects = base / "projects"
        self.root.mkdir()
        self.projects.mkdir()
        (self.root / ".dev-platform.toml").write_text(
            '[paths]\nfriction_log = ".claude/agent-friction.jsonl"\nworktrees = ".claude/worktrees"\n\n'
            '[development_backlog]\nrepository = "acme/backlog"\nproject_label = "project:demo"\n',
            encoding="utf-8",
        )
        self.write_archive()
        self.write_local_sources()

    def write(self, relative: str, value: object) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else dumps(value), encoding="utf-8")
        return path

    def write_archive(self) -> None:
        self.write(f"{ARCHIVE}/.managed-task.json", {
            "change": CHANGE, "imported_at": "2026-01-02T09:10:00+00:00", "target_repository": TARGET,
            "routing_receipt": {"recommended_start_tier": "R2", "task_family": "general", "assurance": "standard"},
        })
        self.write(f"{ARCHIVE}/verification.md", "# Verification\n\nOpenSpec-Verify: PASS\nVerification-Method: manual\n")
        for path, content in COMMITS[-1][2].items():
            self.write(path, content)

    def write_local_sources(self, *, source_issue: str = CHILD) -> None:
        self.write(f".claude/model-routing/{CHANGE}.json", {
            "change": CHANGE, "source_issue": source_issue, "prepared_at": "2026-01-02T09:15:00+00:00", "start_tier": "R2",
            "profile": "standard", "provider": "codex", "rationale": "SECRET-ROUTING-RATIONALE",
            "supervisor": {"provider": "claude", "model": {"value": "opus", "source": "selected"}},
            "execution": {
                "launched": True, "outcome": "completed", "recorded_at": "2026-01-02T09:40:00+00:00",
                "participant": {"provider": "codex", "model": {"value": "gpt-x", "source": "selected"}},
                "efficiency": {"timing": {"elapsed_ms": 1234, "status": "measured"}, "usage": {
                    "input_tokens": {"value": 50, "source": "runtime-confirmed", "status": "measured"},
                    "total_tokens": {"value": None, "source": "unknown", "status": "unknown"},
                }},
            },
            "escalations": [{"at": "2026-01-02T09:20:00+00:00", "from": "routine", "to": "standard", "reason": "SECRET-ESCALATION-REASON"}],
        })
        pre = ".claude/pre-authoring/requirement-7"
        self.write(f"{pre}/state.json", {"id": "requirement-7", "created_at": "2026-01-02T08:10:00+00:00"})
        self.write(f"{pre}/selection.json", {"depth": "full", "routing": "workers"})
        self.write(f"{pre}/add.json", {"unresolved_choices": [
            {"question": "SECRET-ADD-QUESTION", "resolution": "SECRET-ADD-QUESTION", "status": "resolved"},
        ]})
        self.write(f"{pre}/handoff/{CHANGE}.json", {"created_at": "2026-01-02T09:05:00+00:00"})
        self.write(".claude/requirement-integration/requirement-7/alpha-change.json", {
            "requirement": REQUIREMENT, "source_issue": CHILD, "change": CHANGE,
        })
        events = [
            {"id": "e1", "task": CHILD, "branch": "main", "triggers": ["manual-workaround"], "classification": "process-friction",
             "category": "slow-ci", "observation": "SECRET-FRICTION-OBSERVATION", "evidence": "SECRET-FRICTION-OBSERVATION"},
            {"id": "e2", "task": None, "branch": f"agent/{CHANGE}", "triggers": ["repeated-failure"], "classification": "process-friction",
             "category": "flaky", "hypothesis": "SECRET-FRICTION-OBSERVATION"},
            {"id": "e3", "task": REQUIREMENT, "branch": "main", "triggers": ["manual-workaround"], "classification": "tool-friction",
             "category": "handoff", "proposal": "SECRET-FRICTION-OBSERVATION"},
            {"id": "e4", "task": "acme/backlog#99", "branch": "main", "triggers": ["other"], "classification": "process-friction",
             "category": "unrelated"},
        ]
        self.write(".claude/agent-friction.jsonl", "".join(json.dumps(event) + "\n" for event in events) + "not json\n")

    def write_transcript(self, entries: list[dict], name: str = "s1.jsonl", directory: str | None = None) -> Path:
        folder = self.projects / (directory or metrics._sanitize(str(self.root)))
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")
        return path

    def context(self, *, offline: bool = False, gh: FakeGitHub | None = None) -> metrics.Context:
        return metrics.make_context(self.root, offline=offline, claude_projects_dir=self.projects, runner=gh or FakeGitHub())

    def report(self, **kwargs: object) -> dict:
        return metrics.build_report(self.context(**kwargs), REQUIREMENT)


class ValueModelTests(unittest.TestCase):
    def test_unknown_is_never_zero_and_partial_propagates(self) -> None:
        self.assertEqual(metrics.total([])["value"], 0)
        missing = metrics.total([metrics.unknown("source-missing")])
        self.assertEqual((missing["value"], missing["status"], missing["reason"]), (None, "unknown", "source-missing"))
        mixed = metrics.total([metrics.derived(2, ["a"]), metrics.unknown("offline", ["b"])])
        self.assertEqual((mixed["value"], mixed["status"], mixed["sources"]), (2, "partial", ["a", "b"]))
        lower = metrics.total([metrics.derived(1), metrics.partial(3, ["c"], "published-history-lower-bound")])
        self.assertEqual((lower["value"], lower["status"], lower["reason"]), (4, "partial", "published-history-lower-bound"))
        self.assertEqual(metrics.measured(None)["status"], "unknown")
        self.assertEqual(metrics.lower_bound(metrics.unknown("x"), "y")["status"], "unknown")

    def test_durations_only_between_known_timestamps(self) -> None:
        start = metrics.measured("2026-01-02T10:00:00Z", ["a"])
        self.assertEqual(metrics.span(start, metrics.measured("2026-01-02T10:01:30+00:00", ["b"]))["value"], 90.0)
        self.assertEqual(metrics.span(start, metrics.unknown("offline"))["status"], "unknown")


class RequirementReportTests(RequirementMetricsTestCase):
    def test_completed_requirement_is_reported_from_existing_sources(self) -> None:
        report = self.report()
        child = report["children"][0]
        self.assertEqual(report["requirement"]["children_count"]["status"], "measured")
        self.assertEqual(child["change"]["value"], CHANGE)
        self.assertEqual(child["managed"]["start_tier"]["value"], "R2")
        self.assertEqual(child["managed"]["task_family"]["value"], "general")
        self.assertEqual(child["routing"]["supervisor"]["model"]["value"], "opus")
        self.assertEqual(child["routing"]["executor"]["provider"]["value"], "codex")
        self.assertEqual(child["routing"]["escalations"]["count"]["value"], 1)
        self.assertEqual(child["execution_efficiency"]["elapsed_ms"]["value"], 1234)
        self.assertEqual(child["execution_efficiency"]["usage"]["total_tokens"]["status"], "unknown")
        self.assertTrue(child["verification"]["passed"]["value"])
        self.assertEqual(report["cycle"]["total_s"], {"value": 14400.0, "status": "derived", "sources": ["gh:issue:acme/backlog#7"]})
        names = [stage["name"] for stage in report["cycle"]["stages"]]
        self.assertEqual(names[0], "requirement_created")
        self.assertEqual(names[-1], "requirement_closed")
        self.assertIn("depth_selected", report["cycle"]["missing_stages"])
        self.assertEqual(len(report["cycle"]["stage_durations"]), len(names) - 1)
        self.assertTrue(all(item["seconds"]["value"] >= 0 for item in report["cycle"]["stage_durations"]))
        self.assertIn(f"gh:pr:{TARGET}#31@c5", report["sources"])

    def test_review_rounds_are_reconstructed_with_rerun_causes(self) -> None:
        review = self.report()["children"][0]["review"]
        self.assertEqual((review["rounds"]["value"], review["rounds"]["status"]), (3, "partial"))
        self.assertEqual(review["rounds"]["reason"], "published-history-lower-bound")
        causes = [item["cause"]["value"] for item in review["round_details"]]
        self.assertEqual(causes, ["initial", "substantive-candidate-change", "reviewer-unavailable"])
        self.assertEqual(review["reruns_by_cause"]["substantive-candidate-change"]["value"], 1)
        self.assertEqual(review["reruns_by_cause"]["reviewer-unavailable"]["value"], 1)
        self.assertEqual(review["reruns_by_cause"]["process-rerun"]["value"], 0)
        self.assertEqual(review["launches"]["value"], 6, "a post-launch timeout still counts as a launch")
        self.assertEqual(review["round_details"][0]["wall_time_s"]["value"], 300.0)
        self.assertEqual(review["findings"]["material"]["value"], 2)
        perspective = review["round_details"][0]["perspectives"]["spec-fidelity"]
        self.assertEqual((perspective["model"]["value"], perspective["model_source"]["value"]), ("sonnet", "selected"))
        self.assertEqual(perspective["runtime_usage"]["status"], "unknown")
        self.assertEqual(review["dispositions"]["rejected"]["value"], 1)
        self.assertEqual(review["dispositions"]["blocker"]["value"], 0)
        self.assertEqual(review["dispositions"]["material_findings"]["value"], 1)

    def test_same_digest_after_available_round_is_a_process_rerun_and_missing_digest_unknown(self) -> None:
        def versions(*rounds: dict[str, dict]) -> list[metrics.EvidenceVersion]:
            return [
                metrics.EvidenceVersion(f"independent-reviews/{name}.json", json.dumps(report), f"gh:commit:c{index}:x", None)
                for index, reports in enumerate(rounds) for name, report in reports.items()
            ]
        first = pair("a", "D", "2026-01-02T09:00:00Z", "2026-01-02T09:01:00Z")
        rerun = pair("b", "D", "2026-01-02T09:10:00Z", "2026-01-02T09:11:00Z")
        undigested = pair("c", None, "2026-01-02T09:20:00Z", "2026-01-02T09:21:00Z")
        same_request = copy.deepcopy(undigested)
        for name, report in same_request.items():
            report["reviewer"]["launch_id"] = f"again-{name}"
        history = metrics.History(versions=versions(first, rerun, undigested, same_request))
        section, _ = metrics._review(None, [], history, None)
        self.assertEqual([item["cause"]["value"] for item in section["round_details"]], ["initial", "process-rerun", None, None])
        self.assertEqual(section["round_details"][2]["cause"]["reason"], "digest-missing")
        self.assertEqual(section["rounds"]["value"], 4, "a relaunch under the same request is its own round")

    def test_validation_publication_and_ci_cycles_including_after_first_review(self) -> None:
        child = self.report()["children"][0]
        validation = child["validation"]
        self.assertEqual((validation["cycles"]["value"], validation["cycles"]["status"]), (3, "partial"))
        self.assertEqual(validation["full_cycles"]["value"], 1)
        self.assertEqual(validation["total_duration_s"]["value"], 106.0)
        publication = child["publication"]
        self.assertEqual(publication["publication_cycles"]["value"], 2)
        self.assertEqual(publication["queue_blocked_events"]["value"], 1)
        self.assertEqual(publication["prs"][0]["commits"]["value"], 5)
        ci = child["ci"]
        self.assertEqual(ci["runs"]["value"], 5)
        self.assertEqual(ci["distinct_heads"]["value"], 4)
        self.assertEqual(ci["failed_runs"]["value"], 1)
        self.assertEqual(ci["rerun_attempts"]["value"], 1)
        self.assertEqual(ci["wall_time_total_s"]["value"], 1260.0)
        self.assertEqual(ci["by_workflow"]["Code Erosion"]["value"], 1)
        after = child["cycles_after_first_review"]
        self.assertEqual((after["validation"]["value"], after["ci"]["value"]), (2, 3))

    def test_friction_human_stops_and_runtime_groups(self) -> None:
        report = self.report()
        self.assertEqual(report["children"][0]["friction"]["ids"], ["e1", "e2"])
        self.assertEqual(report["friction"]["ids"], ["e1", "e2", "e3"])
        self.assertEqual(report["friction"]["by_trigger"]["manual-workaround"]["value"], 2)
        stops = report["human_stops"]
        self.assertEqual(stops["pre_authoring_decisions"]["value"], 1)
        self.assertEqual(stops["review_blockers"]["value"], 0)
        self.assertEqual(stops["project_blocked"]["status"], "unknown")
        self.assertEqual((stops["total"]["value"], stops["total"]["status"]), (1, "partial"))
        self.assertEqual(report["session_quality"]["codex"], {"runtime": "codex", "status": "unknown", "reason": "unsupported-runtime"})
        self.assertEqual(report["provider_usage"]["executor/codex"]["input_tokens"]["value"], 50)
        self.assertEqual(report["provider_usage"]["reviewer/claude-code-print"]["launches_without_usage"]["value"], 6)

    def test_routing_record_for_another_issue_is_unknown_not_reused(self) -> None:
        self.write_local_sources(source_issue="acme/backlog#99")
        report = self.report()
        routing = report["children"][0]["routing"]
        self.assertEqual(routing["executor"]["provider"]["reason"], "identity-mismatch")
        self.assertIsNone(routing["supervisor"]["model"]["value"])
        self.assertEqual(report["totals"]["executions"]["status"], "unknown")
        self.assertNotIn("executor/codex", report["provider_usage"])

    def test_historical_routing_record_without_efficiency_is_unknown(self) -> None:
        path = self.root / ".claude" / "model-routing" / f"{CHANGE}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        del record["execution"]["efficiency"]
        path.write_text(json.dumps(record), encoding="utf-8")
        efficiency = self.report()["children"][0]["execution_efficiency"]
        self.assertEqual(efficiency["elapsed_ms"]["reason"], "historical-record-without-field")
        self.assertIsNone(efficiency["elapsed_ms"]["value"])

    def test_offline_keeps_local_sections_and_marks_remote_sections_unknown(self) -> None:
        report = self.report(offline=True)
        child = report["children"][0]
        self.assertEqual(report["mode"], "offline")
        self.assertEqual((report["requirement"]["children_count"]["value"], report["requirement"]["children_count"]["status"]), (1, "partial"))
        self.assertEqual(child["publication"]["publication_cycles"]["reason"], "offline")
        self.assertEqual(child["ci"]["runs"]["reason"], "offline")
        self.assertEqual((child["review"]["rounds"]["value"], child["review"]["rounds"]["reason"]), (1, "offline"))
        self.assertEqual(child["managed"]["start_tier"]["value"], "R2")
        self.assertEqual(report["cycle"]["total_s"]["reason"], "offline")
        self.assertEqual(report["totals"]["ci_runs"]["status"], "unknown")

    def test_remote_failure_makes_only_the_dependent_section_unknown(self) -> None:
        report = self.report(gh=FakeGitHub(fail=("actions/runs",)))
        child = report["children"][0]
        self.assertEqual(child["ci"]["runs"]["reason"], "remote-unavailable")
        self.assertEqual(child["review"]["rounds"]["value"], 3)
        self.assertEqual(child["publication"]["publication_cycles"]["value"], 2)
        self.assertTrue(any("simulated failure" in item["reason"] for item in report["diagnostics"]))

    def test_unreadable_requirement_fails_with_an_actionable_message(self) -> None:
        with self.assertRaisesRegex(metrics.RequirementMetricsError, "--offline"):
            self.report(gh=FakeGitHub(fail=("issues/7",)))
        gh = FakeGitHub()
        gh.responses["repos/acme/backlog/issues/7"]["labels"] = []  # type: ignore[index]
        with self.assertRaisesRegex(metrics.RequirementMetricsError, "type:requirement"):
            self.report(gh=gh)

    def test_report_is_read_only_and_never_emits_source_text(self) -> None:
        self.write_transcript([
            transcript_entry("user", "2026-01-02T09:00:00Z", content=f"SECRET-PROMPT-TEXT work on {REQUIREMENT}"),
            assistant("2026-01-02T09:00:10Z", "q1"),
            transcript_entry("user", "2026-01-02T09:00:20Z", content=[
                {"type": "tool_result", "tool_use_id": "t", "is_error": True, "content": "SECRET-TOOL-OUTPUT"}]),
        ])
        before = sorted((path, path.stat().st_mtime_ns) for path in self.root.rglob("*"))
        with mock.patch.object(metrics, "main_root", return_value=self.root):
            for fmt in ("json", "text"):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = metrics.main(["report", "--requirement", REQUIREMENT, "--offline", "--format", fmt,
                                         "--claude-projects-dir", str(self.projects)])
                self.assertEqual(code, 0)
                text = output.getvalue()
                for secret in SECRETS:
                    self.assertNotIn(secret, text)
        online = json.dumps(self.report())
        for secret in SECRETS:
            self.assertNotIn(secret, online)
        self.assertEqual(sorted((path, path.stat().st_mtime_ns) for path in self.root.rglob("*")), before)


class SessionAdapterTests(RequirementMetricsTestCase):
    def counters(self) -> dict:
        return self.report(offline=True)["session_quality"]["claude-code"]

    def test_counters_are_attributed_exactly_and_deduplicated(self) -> None:
        self.write_transcript([
            transcript_entry("user", "2026-01-02T08:00:00Z", content="unrelated before the span"),
            transcript_entry("user", "2026-01-02T09:00:00Z", content=f"SECRET-PROMPT-TEXT start https://github.com/acme/backlog/issues/7"),
            assistant("2026-01-02T09:00:10Z", "q1"),
            assistant("2026-01-02T09:00:11Z", "q1"),
            transcript_entry("user", "2026-01-02T09:00:20Z", content=[
                {"type": "tool_result", "tool_use_id": "t", "is_error": True, "content": "SECRET-TOOL-OUTPUT"}]),
            transcript_entry("user", "2026-01-02T09:00:30Z", content=[{"type": "text", "text": "[Request interrupted by user]"}]),
            transcript_entry("user", "2026-01-02T09:20:00Z", content="SECRET-PROMPT-TEXT continue"),
            transcript_entry("user", "2026-01-02T09:20:05Z", toolDenialKind="user-rejected", content=[
                {"type": "tool_result", "tool_use_id": "t", "is_error": True,
                 "content": "The user doesn't want to proceed with this tool use. SECRET-TOOL-OUTPUT"}]),
            transcript_entry("user", "2026-01-02T09:20:10Z", content="<task-notification>SECRET-PROMPT-TEXT</task-notification>",
                             promptSource="system"),
            assistant("2026-01-02T09:20:20Z", "q2", tool_input={"ref": CHILD, "text": "SECRET-TOOL-INPUT"}),
            transcript_entry("user", "2026-01-02T12:00:00Z", content="after the span, unattributed"),
        ])
        self.write_transcript([
            transcript_entry("user", "2026-01-02T10:00:00Z", session="s2", branch=f"agent/{CHANGE}", content="SECRET-PROMPT-TEXT"),
            assistant("2026-01-02T10:00:30Z", "q3", branch=f"agent/{CHANGE}", session="s2"),
            "not-a-dict",  # type: ignore[list-item]
        ], name="s2.jsonl", directory=metrics._sanitize(str(self.root / ".claude" / "worktrees" / CHANGE)))
        counters = self.counters()
        self.assertEqual(counters["status"], "derived")
        self.assertEqual(counters["attribution"]["sessions"], ["s1", "s2"])
        self.assertEqual(counters["attribution"]["child_branch_entries"], 2)
        self.assertEqual(counters["prompt_turns"]["value"], 3)
        self.assertEqual(counters["interruptions"]["value"], 1)
        self.assertEqual(counters["tool_rejections"]["value"], 1)
        self.assertEqual(counters["tool_errors"]["value"], 1)
        self.assertEqual(counters["reprompts_after_interrupt_or_rejection"]["value"], 1)
        self.assertEqual(counters["session_time_s"]["value"], 1220.0 + 30.0)
        self.assertEqual(counters["active_time_s"]["value"], 10 + 1 + 9 + 10 + 300 + 5 + 5 + 10 + 30)
        self.assertEqual(counters["runtime_usage"]["fields"]["output_tokens"]["value"], 21, "q1 counted once")
        self.assertEqual(counters["unrecognized_entries"]["value"], 1)
        self.assertEqual(counters["prompt_turns"]["sources"], ["claude-transcript:s1", "claude-transcript:s2"])

    def test_span_mentioning_another_requirement_is_partial(self) -> None:
        self.write_transcript([
            transcript_entry("user", "2026-01-02T09:00:00Z", content=f"do {REQUIREMENT}"),
            transcript_entry("user", "2026-01-02T09:01:00Z", content="also acme/backlog#70 please"),
            transcript_entry("user", "2026-01-02T09:02:00Z", content=f"finish {CHILD}"),
        ])
        counters = self.counters()
        self.assertEqual(counters["status"], "partial")
        self.assertEqual(counters["prompt_turns"], {"value": 3, "status": "partial", "sources": ["claude-transcript:s1"], "reason": "shared-session"})

    def test_missing_unrecognized_or_unattributed_transcripts_are_unknown(self) -> None:
        self.assertEqual(self.counters()["reason"], "source-missing")
        self.write_transcript([{"type": "user", "timestamp": "bad"}, {"type": "assistant"}])
        self.assertEqual(self.counters()["reason"], "unsupported-format")
        self.write_transcript([transcript_entry("user", "2026-01-02T09:00:00Z", content="no reference")])
        self.assertEqual(self.counters()["reason"], "no-attributed-sessions")


class AggregateTests(RequirementMetricsTestCase):
    def test_small_groups_are_insufficient_and_nothing_is_scored(self) -> None:
        report = self.report()
        other = copy.deepcopy(report)
        other["requirement"]["ref"] = "acme/backlog#11"
        with mock.patch("model_routing.EFFICIENCY_MIN_PERCENTILE_OBSERVATIONS", 5):
            result = metrics.aggregate([report, other])
        self.assertEqual([row["requirement"] for row in result["rows"]], [REQUIREMENT, "acme/backlog#11"])
        self.assertEqual(result["rows"][0]["metrics"]["ci_cycles"]["value"], 4)
        group = result["groups"]["children_count"]["1"]
        self.assertEqual((group["n"], group["adequacy"]), (2, "insufficient"))
        self.assertNotIn("metrics", group)
        self.assertEqual(result["groups"]["task_family"]["general"]["n"], 2)
        self.assertEqual(result["runtime_groups"]["executor/codex"]["n"], 2)
        self.assertIn("Advisory only", result["advice"])
        keys: set[str] = set()

        def collect(value: object) -> None:
            if isinstance(value, dict):
                keys.update(value)
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(result)
        self.assertFalse({key for key in keys if "score" in key.lower() or "index" in key.lower()})

    def test_adequate_group_reports_medians_only_over_exact_values(self) -> None:
        report = self.report()
        reports = []
        for index in range(5):
            item = copy.deepcopy(report)
            item["requirement"]["ref"] = f"acme/backlog#{20 + index}"
            item["totals"]["ci_cycles"] = metrics.derived(index + 1)
            reports.append(item)
        result = metrics.aggregate(reports)
        group = result["groups"]["start_tier"]["R2"]
        self.assertEqual(group["adequacy"], "adequate")
        self.assertEqual(group["metrics"]["ci_cycles"]["median"], 3)
        self.assertEqual(group["metrics"]["ci_cycles"]["p95"], 5)
        self.assertEqual(group["metrics"]["review_rounds"]["exact"], 0)
        self.assertEqual(group["metrics"]["review_rounds"]["adequacy"], "insufficient")
        text = metrics.render_aggregate_text(result)
        self.assertIn("Group start_tier=R2: n=5 adequacy=adequate", text)

    def test_closed_since_selects_closed_requirements_through_one_search(self) -> None:
        gh = FakeGitHub()
        ctx = self.context(gh=gh)
        gh.responses["search/issues"] = {"items": [{"number": 9}, {"number": 7}]}
        original = gh.__call__

        def search(args: list[str]) -> str:
            if args[-1].startswith("search/issues?"):
                query = args[-1]
                self.assertIn("label%3Atype%3Arequirement", query)
                self.assertIn("label%3Aproject%3Ademo", query)
                self.assertIn("closed%3A%3E%3D2026-01-01", query)
                return json.dumps(gh.responses["search/issues"])
            return original(args)

        ctx.github = metrics.GitHub(search)
        self.assertEqual(metrics.closed_requirements(ctx, "2026-01-01"), ["acme/backlog#7", "acme/backlog#9"])
        with self.assertRaisesRegex(metrics.RequirementMetricsError, "--offline"):
            metrics.closed_requirements(self.context(offline=True), "2026-01-01")


if __name__ == "__main__":
    unittest.main()
