#!/usr/bin/env python3
"""Read-only end-to-end metrics for Business Requirements.

The report composes lifecycle facts that already exist in their own owners:
the Requirement and child Issues, machine-local pre-authoring and
routing/execution records, archived managed provenance, verification,
automated-check and independent review evidence, the published PR history and
publication labels, GitHub Actions runs, the local friction log and, where the
runtime keeps them, Claude Code session transcripts.  It never writes a file,
cache, log, comment, label, Project field or git ref, and never fetches into
the local repository; everything goes to stdout.

Every metric leaf is ``{value, status, sources}`` with status ``measured``,
``derived``, ``partial`` or ``unknown`` (plus ``reason`` when not measured).
Missing or unreadable evidence is unknown, history rebuilt from published
commits is a partial lower bound, and nothing is turned into zero or an
estimate.  Output carries identifiers, timestamps, counts, durations, statuses
and source references only -- never prompts, transcript text, tool payloads,
finding text, rationale or friction prose.  The report is advisory: it
produces no score and changes no routing, budget or lifecycle policy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import independent_review as review
from _platform_common import current_worktree_root, github_cli_env, main_root, read_platform_config, run_git, utc_now
from managed_task import ISSUE_CHANGE_RE, ISSUE_TARGET_RE, ManagedTaskError, issue_ref, repo
from requirement_intake import REQUIREMENT_LABEL, parse_requirement_body, requirement_slug


SCHEMA_VERSION = 1
MEASURED, DERIVED, PARTIAL, UNKNOWN = "measured", "derived", "partial", "unknown"
HISTORY_LOWER_BOUND = "published-history-lower-bound"
STAGES = (
    "requirement_created", "pre_authoring_started", "depth_selected", "handoff_prepared", "child_created",
    "child_imported", "routed", "execution_recorded", "first_review_launched", "last_review_completed",
    "pr_created", "pr_merged", "child_closed", "requirement_closed",
)
# The platform's primary CI workflow: `Platform CI` centrally, `Dev Platform` in managed projects.
PRIMARY_CI_WORKFLOWS = ("Platform CI", "Dev Platform")
FAILED_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}
PUBLICATION_QUEUED = "publication:queued"
PUBLICATION_BLOCKED = "publication:blocked"
FULL_VALIDATION_COMMAND = "run_test_groups.py --all"
REVIEW_EVIDENCE_FILES = (review.REQUEST_FILE, review.DISPOSITIONS_FILE, "automated-checks.json")
MAX_PR_COMMITS = 250
MAX_EVIDENCE_READS = 200
MAX_RUNS = 300
MAX_EVENTS = 300
MAX_SEARCH_PAGES = 10
GH_TIMEOUT_SECONDS = 60
DIAGNOSTIC_LIMIT = 200
ACTIVE_GAP_CAP_SECONDS = 300
# Unavailable-report limitations written before any perspective launched
# (checked first) versus after a launch; anything else is ambiguous.
PRE_LAUNCH_MARKERS = (
    "readiness probe", "is not ready", "could not be resolved", "cannot be resolved", "route provider is unknown",
    "is not supported", "has no independent review adapter", "cannot calculate the candidate diff",
    "cannot snapshot the workspace", "could not start", "cannot be executed", "is not on PATH",
    "is not an executable file",
)
POST_LAUNCH_MARKERS = (
    "timed out", "exited with status", "returned malformed output", "mutated the workspace",
    "left the workspace unchanged",
)
CLAUDE_RUNTIME = "claude-code"
CLAUDE_TRANSCRIPT_RUNTIME = "claude-code-transcript"
CLAUDE_USAGE_FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")
INTERRUPTION_MARKER = "[Request interrupted by user"
REJECTION_MARKER = "The user doesn't want to proceed with this tool use"
USER_REJECTED_DENIAL = "user-rejected"
RUNTIME_TEXT_TAGS = (
    "task-notification", "system-reminder", "ci-monitor-event", "local-command-stdout", "local-command-stderr",
    "local-command-caveat", "bash-stdout", "bash-stderr",
)
ISSUE_REF_RE = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)(?![0-9])")
ISSUE_URL_RE = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)(?![0-9])")
ADVICE = (
    "Advisory only: rows and groups are descriptive evidence, not a score. Any routing, decomposition, budget "
    "or lifecycle policy change requires its own managed change."
)


class RequirementMetricsError(RuntimeError):
    """The Requirement itself cannot be read, so no report can be produced."""


class GitHubUnavailable(RuntimeError):
    """A remote read failed; only the dependent section becomes unknown."""


# Value model ---------------------------------------------------------------


def _source_list(sources: Iterable[str]) -> list[str]:
    return sorted({source for source in sources if source})


def leaf(value: Any, status: str, sources: Iterable[str] = (), reason: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"value": None if status == UNKNOWN else value, "status": status, "sources": _source_list(sources)}
    if reason and status != MEASURED:
        item["reason"] = reason
    return item


def unknown(reason: str, sources: Iterable[str] = ()) -> dict[str, Any]:
    return leaf(None, UNKNOWN, sources, reason)


def measured(value: Any, sources: Iterable[str] = (), *, missing: str = "historical-record-without-field") -> dict[str, Any]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return unknown(missing, sources)
    return leaf(value, MEASURED, sources)


def derived(value: Any, sources: Iterable[str] = ()) -> dict[str, Any]:
    return leaf(value, DERIVED, sources)


def partial(value: Any, sources: Iterable[str], reason: str) -> dict[str, Any]:
    return leaf(value, PARTIAL, sources, reason)


def _first_reason(items: list[dict[str, Any]], default: str) -> str:
    return next((item["reason"] for item in items if item.get("reason")), default)


def total(items: Iterable[dict[str, Any]], *, reason: str = "incomplete-inputs") -> dict[str, Any]:
    """Sum leaves: an unknown input makes the result partial (a lower bound) or unknown, never zero."""
    items = list(items)
    sources = [source for item in items for source in item["sources"]]
    known = [item for item in items if item["status"] != UNKNOWN]
    if not items:
        return derived(0)
    if not known:
        return unknown(_first_reason(items, "source-missing"), sources)
    value = sum(item["value"] for item in known)
    if isinstance(value, float):
        value = round(value, 3)
    if len(known) < len(items):
        return partial(value, sources, reason)
    if any(item["status"] == PARTIAL for item in known):
        return partial(value, sources, _first_reason([item for item in known if item["status"] == PARTIAL], reason))
    return derived(value, sources)


def lower_bound(item: dict[str, Any], reason: str) -> dict[str, Any]:
    """Mark a known value as a lower bound (e.g. history that can miss unpublished attempts)."""
    if item["status"] == UNKNOWN:
        return item
    return partial(item["value"], item["sources"], item.get("reason") if item["status"] == PARTIAL else reason)


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _seconds(start: Any, end: Any) -> float | None:
    begin, finish = _time(start), _time(end)
    if begin is None or finish is None:
        return None
    return round((finish - begin).total_seconds(), 3)


def span(start: dict[str, Any], end: dict[str, Any]) -> dict[str, Any]:
    sources = [*start["sources"], *end["sources"]]
    if start["status"] == UNKNOWN or end["status"] == UNKNOWN:
        return unknown(_first_reason([start, end], "source-missing"), sources)
    seconds = _seconds(start["value"], end["value"])
    if seconds is None:
        return unknown("unreadable", sources)
    if PARTIAL in (start["status"], end["status"]):
        return partial(seconds, sources, _first_reason([start, end], "incomplete-inputs"))
    return derived(seconds, sources)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _bounded(text: str) -> str:
    return " ".join(str(text).split())[:DIAGNOSTIC_LIMIT]


def _canonical_ref(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        repository, number = issue_ref(value)
    except ManagedTaskError:
        return None
    return f"{repository}#{number}"


# Sources -------------------------------------------------------------------


GhRunner = Callable[[list[str]], str]


def gh_runner(root: Path) -> GhRunner:
    """Run read-only ``gh`` calls; authentication is resolved once and never printed."""
    cache: dict[str, Any] = {}

    def run(args: list[str]) -> str:
        if "env" not in cache:
            cache["env"] = github_cli_env(root)
        if cache["env"] is None:
            raise GitHubUnavailable("GitHub CLI authentication is unavailable; run gh auth login")
        try:
            result = subprocess.run(
                ["gh", *args], cwd=root, env=cache["env"], text=True, capture_output=True, timeout=GH_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubUnavailable(f"gh could not complete: {exc}") from exc
        if result.returncode:
            raise GitHubUnavailable(f"gh api failed: {_bounded(result.stderr or result.stdout)}")
        return result.stdout

    return run


class GitHub:
    """Bounded GET-only access to the GitHub REST API through an injectable runner."""

    def __init__(self, runner: GhRunner) -> None:
        self.runner = runner

    def get(self, path: str) -> Any:
        try:
            return json.loads(self.runner(["api", path]))
        except json.JSONDecodeError as exc:
            raise GitHubUnavailable(f"unreadable GitHub response for {path.split('?')[0]}") from exc

    def raw(self, path: str) -> str:
        return self.runner(["api", "-H", "Accept: application/vnd.github.raw", path])

    def pages(self, path: str, *, limit: int, key: str | None = None) -> tuple[list[Any], bool]:
        """Return ``(items, complete)``; ``complete`` is false when ``limit`` cut the listing."""
        items: list[Any] = []
        page = 1
        while True:
            joiner = "&" if "?" in path else "?"
            payload = self.get(f"{path}{joiner}per_page=100&page={page}")
            batch = payload.get(key) if key and isinstance(payload, dict) else payload
            if not isinstance(batch, list):
                raise GitHubUnavailable(f"unexpected GitHub listing for {path.split('?')[0]}")
            items.extend(batch)
            if len(items) >= limit:
                return items[:limit], len(items) == limit and len(batch) < 100
            if len(batch) < 100:
                return items, True
            page += 1


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "source-missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "unreadable"
    return (payload, None) if isinstance(payload, dict) else (None, "unreadable")


@dataclass
class Context:
    root: Path
    github: GitHub | None
    config: dict[str, Any]
    transcripts: "ClaudeTranscripts"
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    diagnostics: list[dict[str, str]] = field(default_factory=list)

    def note(self, section: str, reason: str) -> None:
        self.diagnostics.append({"section": section, "reason": _bounded(reason)})

    def local_ref(self, path: Path) -> str:
        try:
            return "local:" + path.relative_to(self.root / ".claude").as_posix()
        except ValueError:
            return "local:" + path.name

    def file_ref(self, path: Path) -> str:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        except OSError:
            digest = "unreadable"
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            relative = path.name
        return f"file:{relative}@{digest}"

    def remote(self, section: str, call: Callable[[GitHub], Any]) -> tuple[Any, str | None]:
        if self.github is None:
            return None, "offline"
        try:
            return call(self.github), None
        except GitHubUnavailable as exc:
            self.note(section, str(exc))
            return None, "remote-unavailable"


# Requirement and children ---------------------------------------------------


@dataclass
class ChildInfo:
    ref: str
    issue: dict[str, Any] | None = None
    issue_reason: str | None = None
    change: str | None = None
    change_reason: str | None = None
    target: str | None = None
    sources: list[str] = field(default_factory=list)


def _integration_receipts(ctx: Context, number: int, requirement: str) -> list[tuple[dict[str, Any], str]]:
    directory = ctx.root / ".claude" / "requirement-integration" / requirement_slug(number)
    receipts: list[tuple[dict[str, Any], str]] = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        payload, _ = _load(path)
        if payload and _canonical_ref(payload.get("requirement")) == requirement:
            receipts.append((payload, ctx.local_ref(path)))
    return receipts


def _retrospective(ctx: Context, number: int, requirement: str) -> tuple[dict[str, Any] | None, str | None]:
    path = ctx.root / ".claude" / "requirement-retrospective" / f"{requirement_slug(number)}.json"
    payload, _ = _load(path)
    if payload and _canonical_ref(payload.get("requirement")) == requirement:
        return payload, ctx.local_ref(path)
    return None, None


def _child_from_issue(ctx: Context, ref: str) -> ChildInfo:
    info = ChildInfo(ref=ref, sources=[f"gh:issue:{ref}"])
    repository, number = issue_ref(ref)
    issue, reason = ctx.remote(f"child {ref}", lambda gh: gh.get(f"repos/{repository}/issues/{number}"))
    if not isinstance(issue, dict):
        info.issue_reason = reason or "unreadable"
        info.change_reason = info.issue_reason
        return info
    info.issue = issue
    body = str(issue.get("body") or "")
    changes = set(ISSUE_CHANGE_RE.findall(body))
    if len(changes) == 1:
        info.change = changes.pop().strip()
    else:
        info.change_reason = "ambiguous" if changes else "source-missing"
    targets = set(ISSUE_TARGET_RE.findall(body))
    if len(targets) == 1:
        try:
            info.target = repo(targets.pop())
        except ManagedTaskError:
            info.target = None
    return info


def _children(ctx: Context, requirement: str, number: int, issue: dict[str, Any] | None) -> tuple[list[ChildInfo], dict[str, Any]]:
    if issue is not None:
        refs: list[str] = []
        for value in parse_requirement_body(str(issue.get("body") or ""))["children"]:
            ref = _canonical_ref(value)
            if ref and ref not in refs:
                refs.append(ref)
        return [_child_from_issue(ctx, ref) for ref in refs], measured(len(refs), [f"gh:issue:{requirement}"])
    # Offline: exact identities recorded by local integration receipts and the retrospective.
    children: dict[str, ChildInfo] = {}
    for payload, source in _integration_receipts(ctx, number, requirement):
        ref = _canonical_ref(payload.get("source_issue"))
        change = payload.get("change")
        if ref and isinstance(change, str) and change.strip():
            info = children.setdefault(ref, ChildInfo(ref=ref, issue_reason="offline"))
            info.change = change.strip()
            info.sources.append(source)
    retrospective, source = _retrospective(ctx, number, requirement)
    for value in (retrospective or {}).get("children") or []:
        ref = _canonical_ref(value)
        if ref:
            info = children.setdefault(ref, ChildInfo(ref=ref, issue_reason="offline", change_reason="offline"))
            info.sources.append(source or "")
    sources = [source for info in children.values() for source in info.sources]
    count = partial(len(children), sources, "offline") if children else unknown("offline")
    return list(children.values()), count


# Local evidence -------------------------------------------------------------


def _archive(ctx: Context, change: str) -> tuple[Path | None, dict[str, Any] | None, str]:
    """Return ``(path, provenance, state)`` matched by exact managed provenance change."""
    base = ctx.root / "openspec" / "changes"
    pattern = re.compile(r"\d{4}-\d{2}-\d{2}-" + re.escape(change))
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((base / "archive").glob(f"*-{change}")):
        if path.is_dir() and pattern.fullmatch(path.name):
            provenance, _ = _load(path / ".managed-task.json")
            if provenance and provenance.get("change") == change:
                matches.append((path, provenance))
    if len(matches) > 1:
        return None, None, "ambiguous"
    if matches:
        return matches[0][0], matches[0][1], "archived"
    provenance, _ = _load(base / change / ".managed-task.json")
    if provenance and provenance.get("change") == change:
        return base / change, provenance, "active"
    return None, None, "source-missing"


def _managed(ctx: Context, path: Path | None, provenance: dict[str, Any] | None, state: str) -> dict[str, Any]:
    if path is None or provenance is None:
        return {"state": unknown(state), "imported_at": unknown(state), "start_tier": unknown(state),
                "task_family": unknown(state), "assurance": unknown(state)}
    source = ctx.file_ref(path / ".managed-task.json")
    receipt = provenance.get("routing_receipt") if isinstance(provenance.get("routing_receipt"), dict) else {}
    return {
        "state": measured(state, [source]),
        "imported_at": measured(provenance.get("imported_at"), [source]),
        "start_tier": measured(receipt.get("recommended_start_tier"), [source]),
        "task_family": measured(receipt.get("task_family"), [source]),
        "assurance": measured(receipt.get("assurance"), [source]),
    }


def _routing_record(ctx: Context, change: str, child: str) -> tuple[dict[str, Any] | None, str, str | None]:
    path = ctx.root / ".claude" / "model-routing" / f"{change}.json"
    record, reason = _load(path)
    source = ctx.local_ref(path)
    if record is None:
        return None, source, reason
    if record.get("change") != change or _canonical_ref(record.get("source_issue")) != child:
        return None, source, "identity-mismatch"
    return record, source, None


def _participant(execution: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    for key, kind in (("participant", "participant"), ("claimed_participant", "claimed-participant")):
        if isinstance(execution.get(key), dict):
            return execution[key], kind
    return {}, None


def _model_fields(value: Any, sources: list[str]) -> dict[str, Any]:
    model = value if isinstance(value, dict) else {}
    return {"model": measured(model.get("value"), sources), "model_source": measured(model.get("source"), sources)}


def _routing(record: dict[str, Any] | None, source: str, reason: str | None) -> dict[str, Any]:
    if record is None:
        missing = unknown(reason or "source-missing", [source])
        return {"prepared_at": missing, "supervisor": {"provider": missing, "model": missing, "model_source": missing},
                "executor": {"provider": missing, "model": missing, "model_source": missing, "participant": missing,
                             "launched": missing, "launch_evidence": missing, "outcome": missing, "recorded_at": missing},
                "executions": missing, "escalations": {"count": missing, "items": []}}
    sources = [source]
    supervisor = record.get("supervisor") if isinstance(record.get("supervisor"), dict) else {}
    execution = record.get("execution") if isinstance(record.get("execution"), dict) else {}
    participant, kind = _participant(execution)
    launched = execution.get("launched")
    escalations = record.get("escalations")
    items = [
        {"at": measured(item.get("at"), sources), "from": measured(item.get("from"), sources), "to": measured(item.get("to"), sources)}
        for item in escalations if isinstance(item, dict)
    ] if isinstance(escalations, list) else []
    executed = bool(kind) or isinstance(execution.get("outcome"), str)
    return {
        "prepared_at": measured(record.get("prepared_at"), sources),
        "supervisor": {"provider": measured(supervisor.get("provider"), sources), **_model_fields(supervisor.get("model"), sources)},
        "executor": {
            "provider": measured(participant.get("provider"), sources),
            **_model_fields(participant.get("model"), sources),
            "participant": measured(kind, sources),
            "launched": measured(launched if isinstance(launched, bool) else None, sources),
            "launch_evidence": measured(execution.get("launch_evidence"), sources),
            "outcome": measured(execution.get("outcome"), sources),
            "recorded_at": measured(execution.get("recorded_at"), sources),
        },
        "executions": derived(1 if executed else 0, sources),
        "escalations": {
            "count": derived(len(items), sources) if isinstance(escalations, list) else unknown("historical-record-without-field", sources),
            "items": items,
        },
    }


def _usage_leaf(value: Any, sources: list[str]) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("status") == "measured" and _int(value.get("value")) is not None:
        return measured(value["value"], sources)
    return unknown("runtime-unavailable", sources)


def _execution_efficiency(record: dict[str, Any] | None, source: str, reason: str | None) -> dict[str, Any]:
    if record is None:
        return {"runtime": None, "elapsed_ms": unknown(reason or "source-missing", [source]), "usage": {}}
    sources = [source]
    execution = record.get("execution") if isinstance(record.get("execution"), dict) else {}
    participant, _ = _participant(execution)
    runtime = participant.get("provider") if isinstance(participant.get("provider"), str) else None
    efficiency = execution.get("efficiency")
    if not isinstance(efficiency, dict):
        return {"runtime": runtime, "elapsed_ms": unknown("historical-record-without-field", sources), "usage": {}}
    timing = efficiency.get("timing") if isinstance(efficiency.get("timing"), dict) else {}
    elapsed = _int(timing.get("elapsed_ms")) if timing.get("status") == "measured" else None
    usage = efficiency.get("usage") if isinstance(efficiency.get("usage"), dict) else {}
    return {
        "runtime": runtime,
        "elapsed_ms": measured(elapsed, sources, missing="runtime-unavailable"),
        "usage": {name: _usage_leaf(value, sources) for name, value in sorted(usage.items())},
    }


def _verification(ctx: Context, path: Path | None, state: str) -> dict[str, Any]:
    if path is None:
        missing = unknown(state)
        return {"receipt_present": missing, "passed": missing, "method_present": missing}
    receipt = path / "verification.md"
    if not receipt.is_file():
        source = ctx.file_ref(path / ".managed-task.json")
        return {"receipt_present": measured(False, [source]), "passed": unknown("source-missing", [source]),
                "method_present": unknown("source-missing", [source])}
    source = ctx.file_ref(receipt)
    try:
        text = receipt.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"receipt_present": measured(True, [source]), "passed": unknown("unreadable", [source]),
                "method_present": unknown("unreadable", [source])}
    verdict = re.search(r"^OpenSpec-Verify:\s*(\S+)", text, re.MULTILINE)
    method = re.search(r"^Verification-Method:\s*\S", text, re.MULTILINE)
    return {
        "receipt_present": measured(True, [source]),
        "passed": measured(verdict.group(1).upper() == "PASS", [source]) if verdict else unknown("source-missing", [source]),
        "method_present": measured(bool(method), [source]),
    }


# Published PR history -------------------------------------------------------


@dataclass
class EvidenceVersion:
    file: str
    content: str
    source: str
    committed_at: str | None


@dataclass
class History:
    versions: list[EvidenceVersion] = field(default_factory=list)
    reason: str | None = None
    complete: bool = True


def _evidence_file(change: str, path: str) -> str | None:
    match = re.fullmatch(
        r"openspec/changes/(?:archive/\d{4}-\d{2}-\d{2}-)?" + re.escape(change) + r"/(?P<file>.+)", path,
    )
    if not match:
        return None
    name = match.group("file")
    if name in REVIEW_EVIDENCE_FILES or re.fullmatch(re.escape(review.REPORTS_DIR) + r"/[A-Za-z0-9_.-]+\.json", name):
        return name
    return None


def _pull_requests(ctx: Context, target: str | None, change: str, reason: str | None = None, branch_refs: list[str] | None = None) -> tuple[list[dict[str, Any]] | None, str | None]:
    if target is None:
        return None, reason or ("source-missing" if ctx.github is not None else "offline")
    owner = target.split("/")[0]
    prs: dict[int, dict[str, Any]] = {}
    for branch_ref in branch_refs or [f"agent/{change}"]:
        branch = urllib.parse.quote(f"{owner}:{branch_ref}", safe=":/")
        items, reason = ctx.remote(
            f"pull requests for {change}",
            lambda gh: gh.pages(f"repos/{target}/pulls?state=all&head={branch}", limit=100)[0],
        )
        if items is None:
            return None, reason
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("number"), int):
                prs[item["number"]] = item
    return [prs[number] for number in sorted(prs)], None


def _history(ctx: Context, target: str, change: str, prs: list[dict[str, Any]]) -> tuple[History, dict[int, int]]:
    """Read every published version of the change's review and automated-check evidence."""
    history = History()
    commit_counts: dict[int, int] = {}
    reads = 0
    listed = 0
    for pr in prs:
        number = pr["number"]
        commits, reason = ctx.remote(
            f"commits of {target}#{number}",
            lambda gh: gh.pages(f"repos/{target}/pulls/{number}/commits", limit=MAX_PR_COMMITS - listed),
        )
        if commits is None:
            history.reason = reason
            history.complete = False
            continue
        items, complete = commits
        history.complete = history.complete and complete
        commit_counts[number] = len(items)
        listed += len(items)
        for commit in items:
            sha = commit.get("sha") if isinstance(commit, dict) else None
            if not isinstance(sha, str):
                continue
            committed_at = ((commit.get("commit") or {}).get("committer") or {}).get("date")
            detail, reason = ctx.remote(f"commit {sha[:12]}", lambda gh: gh.get(f"repos/{target}/commits/{sha}"))
            if not isinstance(detail, dict):
                history.reason = reason or "unreadable"
                history.complete = False
                continue
            for entry in detail.get("files") or []:
                path = entry.get("filename") if isinstance(entry, dict) else None
                name = _evidence_file(change, path) if isinstance(path, str) else None
                if name is None or entry.get("status") == "removed":
                    continue
                if reads >= MAX_EVIDENCE_READS:
                    history.complete = False
                    history.reason = "bounded"
                    continue
                reads += 1
                quoted = urllib.parse.quote(path)
                content, reason = ctx.remote(f"{path} at {sha[:12]}", lambda gh: gh.raw(f"repos/{target}/contents/{quoted}?ref={sha}"))
                if content is None:
                    history.reason = reason
                    history.complete = False
                    continue
                history.versions.append(EvidenceVersion(name, content, f"gh:commit:{sha}:{path}", committed_at))
        if listed >= MAX_PR_COMMITS:
            history.complete = False
            history.reason = history.reason or "bounded"
            break
    return history, commit_counts


def _history_reason(history: History | None, fallback: str | None) -> str:
    """Why reconstructed counts are a lower bound."""
    if history is None:
        return fallback or "source-missing"
    return HISTORY_LOWER_BOUND if history.complete else (history.reason or HISTORY_LOWER_BOUND)


def _archive_versions(ctx: Context, path: Path | None) -> list[EvidenceVersion]:
    if path is None:
        return []
    versions: list[EvidenceVersion] = []
    names = [*REVIEW_EVIDENCE_FILES, *(f"{review.REPORTS_DIR}/{perspective}.json" for perspective in review.PERSPECTIVES)]
    for name in names:
        file = path / name
        if file.is_file():
            try:
                versions.append(EvidenceVersion(name, file.read_text(encoding="utf-8"), ctx.file_ref(file), None))
            except (OSError, UnicodeDecodeError):
                ctx.note(f"archive {path.name}", f"unreadable {name}")
    return versions


def _json_object(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


# Independent review ---------------------------------------------------------


def _launch_identity(report: dict[str, Any]) -> Any:
    reviewer = report.get("reviewer") if isinstance(report.get("reviewer"), dict) else {}
    return reviewer.get("launch_id") or reviewer.get("context_id") or report.get("launched_at")


def _rounds(versions: list[EvidenceVersion]) -> list[dict[str, Any]]:
    """Group report versions into rounds by request id in commit order.

    A perspective reported again under the same request with a different
    launch identity is a separate rerun round.
    """
    rounds: list[dict[str, Any]] = []
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for version in versions:
        if not version.file.startswith(review.REPORTS_DIR + "/"):
            continue
        report = _json_object(version.content)
        if report is None:
            continue
        perspective = report.get("perspective") or Path(version.file).stem
        key = (perspective, report.get("request_id"), _launch_identity(report))
        if key in seen:
            seen[key]["sources"].append(version.source)
            continue
        current = rounds[-1] if rounds else None
        if current is None or current["request_id"] != report.get("request_id") or perspective in current["reports"]:
            current = {"request_id": report.get("request_id"), "reports": {}, "sources": []}
            rounds.append(current)
        current["reports"][perspective] = report
        current["sources"].append(version.source)
        seen[key] = current
    return rounds


def _launched(report: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    reviewer = report.get("reviewer") if isinstance(report.get("reviewer"), dict) else {}
    if reviewer.get("launch_evidence") != review.PLATFORM_OBSERVED:
        return unknown("launch-not-platform-observed", sources)
    if report.get("availability") == "available":
        return derived(1, sources)
    limitation = str(report.get("limitation") or "")
    if any(marker in limitation for marker in PRE_LAUNCH_MARKERS):
        return derived(0, sources)
    if any(marker in limitation for marker in POST_LAUNCH_MARKERS):
        return derived(1, sources)
    return unknown("ambiguous-limitation", sources)


def _usage_view(report: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    usage = review.read_runtime_usage(report)
    if usage["status"] != "measured":
        return {"runtime": usage["runtime"], "status": UNKNOWN, "reason": usage.get("reason"), "fields": {}}
    return {"runtime": usage["runtime"], "status": MEASURED,
            "fields": {name: _usage_leaf(value, sources) for name, value in sorted(usage["fields"].items())}}


def _perspective(report: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    reviewer = report.get("reviewer") if isinstance(report.get("reviewer"), dict) else {}
    findings = report.get("findings") if isinstance(report.get("findings"), list) else None
    launched_at, completed_at = measured(report.get("launched_at"), sources), measured(report.get("completed_at"), sources)
    counts: dict[str, dict[str, Any]] = {}
    for severity in sorted(review.FINDING_SEVERITIES):
        if findings is None:
            counts[severity] = unknown("unreadable", sources)
        else:
            counts[severity] = derived(sum(1 for item in findings if isinstance(item, dict) and item.get("severity") == severity), sources)
    return {
        "provider": measured(reviewer.get("provider"), sources),
        "runtime": measured(reviewer.get("runtime"), sources),
        **_model_fields(reviewer.get("model"), sources),
        "availability": measured(report.get("availability"), sources),
        "launch_evidence": measured(reviewer.get("launch_evidence"), sources),
        "launched": _launched(report, sources),
        "launched_at": launched_at,
        "completed_at": completed_at,
        "wall_time_s": span(launched_at, completed_at),
        "findings": counts,
        "runtime_usage": _usage_view(report, sources),
    }


def _round_cause(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    if previous is None:
        return "initial"
    before, after = previous.get("digest"), current.get("digest")
    if not before or not after:
        return "unknown"
    if before != after:
        return "substantive-candidate-change"
    if any(report.get("availability") != "available" for report in previous["reports"].values()):
        return "reviewer-unavailable"
    return "process-rerun"


def _round_times(round_: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    launched = [_time(report.get("launched_at")) for report in round_["reports"].values()]
    completed = [_time(report.get("completed_at")) for report in round_["reports"].values()]
    start = min(launched) if launched and all(launched) else None
    end = max(completed) if completed and all(completed) else None
    return start, end


def _review(archive: str | None, archived: list[EvidenceVersion], history: History | None,
            history_reason: str | None) -> tuple[dict[str, Any], datetime | None]:
    versions = [*(history.versions if history else []), *archived]
    rounds = _rounds(versions)
    lower = _history_reason(history, history_reason)
    details: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for index, round_ in enumerate(rounds, start=1):
        digests = {report.get("task_content_digest") for report in round_["reports"].values()}
        round_["digest"] = digests.pop() if len(digests) == 1 else None
        sources = round_["sources"]
        perspectives = {name: _perspective(report, sources) for name, report in sorted(round_["reports"].items())}
        start, end = _round_times(round_)
        cause = _round_cause(previous, round_)
        details.append({
            "round": index,
            "request_id": measured(round_["request_id"], sources),
            "task_content_digest": measured(round_["digest"], sources, missing="ambiguous"),
            "cause": derived(cause, sources) if cause != "unknown" else unknown("digest-missing", sources),
            "launches": total(item["launched"] for item in perspectives.values()),
            "wall_time_s": derived(round((end - start).total_seconds(), 3), sources) if start and end else unknown("source-missing", sources),
            "perspectives": perspectives,
        })
        previous = round_
    if not rounds and history is None and archive is None:
        count = unknown(lower)
    else:
        count = partial(len(rounds), [source for item in rounds for source in item["sources"]] or [archive or ""], lower)
    causes = ("substantive-candidate-change", "reviewer-unavailable", "process-rerun", "unknown")
    reruns = {
        cause: lower_bound(derived(
            sum(1 for item in details if (item["cause"]["value"] or "unknown") == cause and item["round"] > 1),
            [source for item in details[1:] for source in item["cause"]["sources"]],
        ), lower) if count["status"] != UNKNOWN else unknown(lower)
        for cause in causes
    }
    dispositions = _dispositions(archive, versions, rounds, details, lower)
    first_completed = _round_times(rounds[0])[1] if rounds else None
    perspectives = [p for item in details for p in item["perspectives"].values()]
    section = {
        "rounds": count,
        "launches": lower_bound(total(item["launches"] for item in details), lower) if count["status"] != UNKNOWN else unknown(lower),
        "wall_time_s": lower_bound(total(item["wall_time_s"] for item in details), lower) if count["status"] != UNKNOWN else unknown(lower),
        "findings": {
            severity: lower_bound(total(p["findings"][severity] for p in perspectives), lower) if count["status"] != UNKNOWN else unknown(lower)
            for severity in sorted(review.FINDING_SEVERITIES)
        },
        "reruns_by_cause": reruns,
        "dispositions": dispositions,
        "round_details": details,
    }
    return section, first_completed


def _disposition_items(versions: list[EvidenceVersion]) -> tuple[list[tuple[dict[str, Any], str]], bool, bool]:
    """Distinct dispositions across every published record version: ``(items, seen, readable)``.

    ``dispose`` replaces an earlier disposition of the same finding, so older
    rounds' dispositions survive only in earlier published versions; the latest
    version of the same binding wins.
    """
    items: dict[tuple[Any, ...], tuple[dict[str, Any], str]] = {}
    seen = False
    readable = True
    for version in versions:
        if version.file != review.DISPOSITIONS_FILE:
            continue
        seen = True
        payload = _json_object(version.content)
        entries = payload.get("dispositions") if payload else None
        if not isinstance(entries, list):
            readable = False
            continue
        for item in entries:
            if isinstance(item, dict):
                key = (item.get("request_id"), item.get("perspective"), item.get("finding"), item.get("report_sha256"))
                items[key] = (item, version.source)
    return list(items.values()), seen, readable


def _disposition_round(item: dict[str, Any], rounds: list[dict[str, Any]]) -> int | None:
    """The round a disposition binds to: its report digest, else a unique request id; ``None`` when ambiguous."""
    perspective = item.get("perspective")
    digest = item.get("report_sha256")
    if digest:
        matches = [
            index for index, round_ in enumerate(rounds)
            if perspective in round_["reports"] and review.report_digest(round_["reports"][perspective]) == digest
        ]
        if len(matches) == 1:
            return matches[0]
    request = item.get("request_id")
    matches = [index for index, round_ in enumerate(rounds) if request and round_["request_id"] == request and perspective in round_["reports"]]
    return matches[0] if len(matches) == 1 else None


def _dispositions(archive: str | None, versions: list[EvidenceVersion], rounds: list[dict[str, Any]],
                  details: list[dict[str, Any]], lower: str) -> dict[str, Any]:
    """Attach per-round disposition counts to ``details`` and return the child-level aggregate."""
    items, seen, readable = _disposition_items(versions)
    bound = [(item, source, _disposition_round(item, rounds)) for item, source in items]
    unbound = any(index is None for _, _, index in bound)
    for index, detail in enumerate(details):
        material = total(p["findings"]["material"] for p in detail["perspectives"].values())
        mine = [(item, source) for item, source, bound_index in bound if bound_index == index]
        sources = [*rounds[index]["sources"], *(source for _, source in mine)]
        if not readable or unbound:
            why = "unreadable" if not readable else "unbound-disposition"
            rejected = blocker = unknown(why, sources)
        elif not seen and archive is None:
            rejected = blocker = unknown("source-missing", sources)
        else:
            statuses = [item.get("status") for item, _ in mine]
            rejected = lower_bound(derived(statuses.count("rejected"), sources), lower)
            blocker = lower_bound(derived(statuses.count("blocker"), sources), lower)
        detail["dispositions"] = {"material_findings": material, "rejected": rejected, "blocker": blocker}
    material_total = lower_bound(total(detail["dispositions"]["material_findings"] for detail in details), lower) if details else unknown("source-missing")
    all_sources = [source for _, source in items]
    if not readable:
        broken = unknown("unreadable", all_sources)
        return {"material_findings": material_total, "rejected": broken, "blocker": broken}
    if not seen:
        if archive is None:
            missing = unknown("source-missing")
            return {"material_findings": material_total, "rejected": missing, "blocker": missing}
        # A delivered change without a disposition record had nothing disposed.
        sources = rounds[-1]["sources"] if rounds else [archive]
        return {"material_findings": material_total, "rejected": lower_bound(derived(0, sources), lower),
                "blocker": lower_bound(derived(0, sources), lower)}
    statuses = [item.get("status") for item, _ in items]
    return {
        "material_findings": material_total,
        "rejected": lower_bound(derived(statuses.count("rejected"), all_sources), lower),
        "blocker": lower_bound(derived(statuses.count("blocker"), all_sources), lower),
    }


# Validation, publication and CI ---------------------------------------------


def _seconds_value(item: Any) -> float | None:
    value = item.get("duration_seconds") if isinstance(item, dict) else None
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None


def _validation(archive: Path | None, history: History | None, history_reason: str | None, archived: list[EvidenceVersion]) -> dict[str, Any]:
    versions = [*(history.versions if history else []), *archived]
    lower = _history_reason(history, history_reason)
    cycles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for version in versions:
        if version.file != "automated-checks.json":
            continue
        digest = hashlib.sha256(version.content.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        sources = [version.source]
        payload = _json_object(version.content)
        commands = payload.get("executed_commands") if payload else None
        if not isinstance(commands, list):
            cycles.append({"committed_at": measured(version.committed_at, sources, missing="source-missing"),
                           "outcome": unknown("unreadable", sources), "full": unknown("unreadable", sources),
                           "duration_s": unknown("unreadable", sources), "commands": unknown("unreadable", sources)})
            continue
        durations = [measured(_seconds_value(item), sources) for item in commands]
        names = [str(item.get("command") or "") for item in commands if isinstance(item, dict)]
        cycles.append({
            "committed_at": measured(version.committed_at, sources, missing="source-missing"),
            "outcome": measured(payload.get("outcome"), sources),
            "full": derived(any(FULL_VALIDATION_COMMAND in name for name in names), sources),
            "duration_s": total(durations),
            "commands": derived(len(commands), sources),
        })
    if not cycles and history is None and archive is None:
        missing = unknown(lower)
        return {"cycles": missing, "full_cycles": missing, "total_duration_s": missing, "cycle_details": []}
    sources = [source for cycle in cycles for source in cycle["commands"]["sources"]]
    full = [cycle for cycle in cycles if cycle["full"]["value"] is True]
    return {
        "cycles": partial(len(cycles), sources, lower),
        "full_cycles": partial(len(full), sources, lower) if all(cycle["full"]["status"] != UNKNOWN for cycle in cycles)
        else partial(len(full), sources, "unreadable"),
        "total_duration_s": lower_bound(total(cycle["duration_s"] for cycle in cycles), lower),
        "cycle_details": cycles,
    }


def _publication(ctx: Context, target: str | None, prs: list[dict[str, Any]] | None, reason: str | None,
                 commit_counts: dict[int, int]) -> dict[str, Any]:
    if prs is None:
        missing = unknown(reason or "source-missing")
        return {"prs": [], "pr_count": missing, "publication_cycles": missing, "queue_blocked_events": missing}
    items: list[dict[str, Any]] = []
    queued: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for pr in prs:
        number = pr["number"]
        head = (pr.get("head") or {}).get("sha") if isinstance(pr.get("head"), dict) else None
        source = f"gh:pr:{target}#{number}@{head or 'unknown'}"
        state = "merged" if pr.get("merged_at") else pr.get("state")
        items.append({
            "number": number,
            "state": measured(state, [source]),
            "created_at": measured(pr.get("created_at"), [source]),
            "merged_at": measured(pr.get("merged_at"), [source], missing="not-merged"),
            "head": measured(head, [source]),
            "commits": derived(commit_counts[number], [source]) if number in commit_counts else unknown("remote-unavailable", [source]),
        })
        events, event_reason = ctx.remote(
            f"publication events of {target}#{number}",
            lambda gh: gh.pages(f"repos/{target}/issues/{number}/events", limit=MAX_EVENTS)[0],
        )
        if events is None:
            queued.append(unknown(event_reason or "unreadable", [source]))
            blocked.append(unknown(event_reason or "unreadable", [source]))
            continue
        labels = [
            (event.get("label") or {}).get("name") for event in events
            if isinstance(event, dict) and event.get("event") == "labeled" and isinstance(event.get("label"), dict)
        ]
        queued.append(derived(labels.count(PUBLICATION_QUEUED), [source]))
        blocked.append(derived(labels.count(PUBLICATION_BLOCKED), [source]))
    pr_sources = [source for item in items for source in item["state"]["sources"]]
    return {
        "prs": items,
        "pr_count": derived(len(items), pr_sources) if items else derived(0),
        "publication_cycles": total(queued),
        "queue_blocked_events": total(blocked),
    }


def _ci(ctx: Context, target: str | None, change: str, reason: str | None = None, branch_refs: list[str] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    if target is None:
        missing = unknown(reason or ("source-missing" if ctx.github is not None else "offline"))
        return {"runs": missing, "by_workflow": {}, "distinct_heads": missing, "failed_runs": missing,
                "rerun_attempts": missing, "wall_time_total_s": missing}, None
    runs: list[dict[str, Any]] = []
    seen: set[Any] = set()
    complete = True
    for branch_ref in branch_refs or [f"agent/{change}"]:
        branch = urllib.parse.quote(branch_ref, safe="")
        listing, reason = ctx.remote(
            f"CI runs for {change}",
            lambda gh: gh.pages(f"repos/{target}/actions/runs?branch={branch}", limit=MAX_RUNS, key="workflow_runs"),
        )
        if listing is None:
            missing = unknown(reason or "unreadable")
            return {"runs": missing, "by_workflow": {}, "distinct_heads": missing, "failed_runs": missing,
                    "rerun_attempts": missing, "wall_time_total_s": missing}, None
        items, branch_complete = listing
        complete = complete and branch_complete
        for run in items:
            if isinstance(run, dict) and run.get("id") not in seen:
                seen.add(run.get("id"))
                runs.append(run)
    sources = [f"gh:run:{run.get('id')}" for run in runs]

    def count(value: int, items: list[str]) -> dict[str, Any]:
        return derived(value, items) if complete else partial(value, items, "bounded")

    by_workflow: dict[str, dict[str, Any]] = {}
    for name in sorted({str(run.get("name") or "unknown") for run in runs}):
        selected = [f"gh:run:{run.get('id')}" for run in runs if str(run.get("name") or "unknown") == name]
        by_workflow[name] = count(len(selected), selected)
    primary = [run for run in runs if run.get("name") in PRIMARY_CI_WORKFLOWS]
    durations = [
        span(measured(run.get("run_started_at"), [f"gh:run:{run.get('id')}"]), measured(run.get("updated_at"), [f"gh:run:{run.get('id')}"]))
        if run.get("status") == "completed" else unknown("in-progress", [f"gh:run:{run.get('id')}"])
        for run in runs
    ]
    attempts = [_int(run.get("run_attempt")) for run in runs]
    section = {
        "runs": count(len(runs), sources),
        "by_workflow": by_workflow,
        "distinct_heads": count(len({run.get("head_sha") for run in primary if run.get("head_sha")}),
                                [f"gh:run:{run.get('id')}" for run in primary]),
        "failed_runs": count(sum(1 for run in runs if run.get("conclusion") in FAILED_CONCLUSIONS), sources),
        "rerun_attempts": count(sum(max(value - 1, 0) for value in attempts if value), sources)
        if all(value is not None for value in attempts) else partial(sum(max(value - 1, 0) for value in attempts if value), sources, "historical-record-without-field"),
        "wall_time_total_s": total(durations) if complete else lower_bound(total(durations), "bounded"),
    }
    return section, primary


def _cycles_after_first_review(first: datetime | None, validation: dict[str, Any], primary_runs: list[dict[str, Any]] | None,
                               ci_reason: str | None) -> dict[str, Any]:
    if first is None:
        missing = unknown("no-review-round")
        return {"validation": missing, "ci": missing}
    after: list[dict[str, Any]] = []
    for cycle in validation.get("cycle_details", []):
        at = _time(cycle["committed_at"]["value"])
        if at is None:
            after.append(unknown("source-missing", cycle["committed_at"]["sources"]))
        else:
            after.append(derived(1 if at > first else 0, cycle["committed_at"]["sources"]))
    validation_after = lower_bound(total(after), HISTORY_LOWER_BOUND)
    if primary_runs is None:
        ci_after = unknown(ci_reason or "source-missing")
    else:
        run_sources = [f"gh:run:{run.get('id')}" for run in primary_runs]
        started = [(run.get("head_sha"), _time(run.get("run_started_at"))) for run in primary_runs if run.get("head_sha")]
        heads = {head for head, at in started if at is not None and at > first}
        ci_after = (derived(len(heads), run_sources) if all(at is not None for _, at in started)
                    else partial(len(heads), run_sources, "historical-record-without-field"))
    return {"validation": validation_after, "ci": ci_after}


# Friction and pre-authoring -------------------------------------------------


def _friction_events(ctx: Context) -> tuple[list[dict[str, Any]] | None, str]:
    relative = str((ctx.config.get("paths") or {}).get("friction_log", ".claude/agent-friction.jsonl"))
    path = (ctx.root / relative).resolve()
    source = ctx.local_ref(path)
    if not path.is_file():
        return None, source
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None, source
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and isinstance(event.get("id"), str):
            events.append(event)
    return events, source


def _friction_summary(events: list[dict[str, Any]] | None, source: str) -> dict[str, Any]:
    if events is None:
        missing = unknown("source-missing", [source])
        return {"count": missing, "by_trigger": {}, "by_classification": {}, "by_category": {}, "ids": []}
    unique = {event["id"]: event for event in events}
    triggers: dict[str, int] = {}
    classifications: dict[str, int] = {}
    categories: dict[str, int] = {}
    for event in unique.values():
        for trigger in event.get("triggers") if isinstance(event.get("triggers"), list) else []:
            triggers[str(trigger)] = triggers.get(str(trigger), 0) + 1
        for value, bucket in ((event.get("classification"), classifications), (event.get("category"), categories)):
            label = str(value) if isinstance(value, str) and value else "unknown"
            bucket[label] = bucket.get(label, 0) + 1
    return {
        "count": derived(len(unique), [source]),
        "by_trigger": {key: derived(value, [source]) for key, value in sorted(triggers.items())},
        "by_classification": {key: derived(value, [source]) for key, value in sorted(classifications.items())},
        "by_category": {key: derived(value, [source]) for key, value in sorted(categories.items())},
        "ids": sorted(unique),
    }


def _child_friction(events: list[dict[str, Any]] | None, child: str, change: str | None, branch_refs: list[str] | None = None) -> list[dict[str, Any]] | None:
    if events is None:
        return None
    matched = []
    for event in events:
        run = event.get("run") if isinstance(event.get("run"), dict) else {}
        if (
            _canonical_ref(event.get("task")) == child
            or (change and event.get("branch") in {f"agent/{change}", *(branch_refs or [])})
            or _canonical_ref(run.get("source_issue")) == child
            or (change and run.get("change") == change)
        ):
            matched.append(event)
    return matched


def _pre_authoring(ctx: Context, number: int) -> dict[str, Any]:
    directory = ctx.root / ".claude" / "pre-authoring" / requirement_slug(number)
    state, state_reason = _load(directory / "state.json")
    if state is not None and state.get("id") != requirement_slug(number):
        state, state_reason = None, "identity-mismatch"
    selection, selection_reason = _load(directory / "selection.json")
    add, _ = _load(directory / "add.json")
    handoffs: list[tuple[str, str]] = []
    for path in sorted((directory / "handoff").glob("*.json")) if (directory / "handoff").is_dir() else []:
        payload, _ = _load(path)
        if payload and _time(payload.get("created_at")):
            handoffs.append((payload["created_at"], ctx.local_ref(path)))
    direct = (directory / "direct-handoff.json").is_file()
    skip = (directory / "skip.json").is_file()
    state_source = [ctx.local_ref(directory / "state.json")]
    selection_source = [ctx.local_ref(directory / "selection.json")]
    if add is not None:
        choices = [item for item in add.get("unresolved_choices") or [] if isinstance(item, dict)]
        add_source = [ctx.local_ref(directory / "add.json")]
        decisions = derived(sum(1 for item in choices if item.get("status") == "resolved"), add_source)
        open_decisions = derived(sum(1 for item in choices if item.get("status") != "resolved"), add_source)
    elif skip or direct:
        # A deterministic direct handoff has no ADD stage, so no design decision could stop it.
        skip_source = [ctx.local_ref(directory / ("skip.json" if skip else "direct-handoff.json"))]
        decisions, open_decisions = derived(0, skip_source), derived(0, skip_source)
    else:
        decisions = open_decisions = unknown("source-missing", [ctx.local_ref(directory)])
    earliest = min(handoffs) if handoffs else None
    return {
        "started_at": measured(state.get("created_at"), state_source) if state else unknown(state_reason or "source-missing", state_source),
        "depth": measured(selection.get("depth"), selection_source) if selection else unknown(selection_reason or "source-missing", selection_source),
        "routing": measured(selection.get("routing"), selection_source) if selection else unknown(selection_reason or "source-missing", selection_source),
        "depth_selected_at": measured(selection.get("created_at") or selection.get("selected_at"), selection_source)
        if selection else unknown(selection_reason or "source-missing", selection_source),
        "handoff_kind": measured("direct" if direct else ("add" if handoffs else None), [ctx.local_ref(directory)], missing="source-missing"),
        "handoff_prepared_at": measured(earliest[0], [earliest[1]]) if earliest else unknown("source-missing", [ctx.local_ref(directory)]),
        "decisions_answered": decisions,
        "decisions_open": open_decisions,
    }


# Claude Code session adapter ------------------------------------------------


def _sanitize(path: str) -> str:
    """Claude Code's project directory name for an absolute path."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


@dataclass(frozen=True)
class SessionEntry:
    session: str
    at: datetime
    branch: str | None
    human_prompt: bool
    interruption: bool
    rejections: int
    errors: int
    usage_key: str | None
    usage: tuple[tuple[str, int], ...]
    refs: frozenset[str]


def _refs(texts: Iterable[str]) -> frozenset[str]:
    found: set[str] = set()
    for text in texts:
        for pattern in (ISSUE_REF_RE, ISSUE_URL_RE):
            for match in pattern.finditer(text):
                found.add(f"{match.group(1).lower()}#{match.group(2)}")
    return frozenset(found)


def _block_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    return ""


def _runtime_text(text: str) -> bool:
    match = re.match(r"\s*<([A-Za-z_-]+)>", text)
    return bool(match and match.group(1) in RUNTIME_TEXT_TAGS)


def _parse_entry(raw: dict[str, Any]) -> SessionEntry | None:
    """Reduce one transcript entry to counters and reference identities; no text leaves this function."""
    kind = raw.get("type")
    at = _time(raw.get("timestamp"))
    session = raw.get("sessionId")
    message = raw.get("message")
    if at is None or not isinstance(session, str) or not session or not isinstance(message, dict):
        return None
    content = message.get("content")
    branch = raw.get("gitBranch") if isinstance(raw.get("gitBranch"), str) else None
    if kind == "user":
        texts: list[str] = []
        tool_results = rejections = errors = 0
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    texts.append(block["text"])
                elif block.get("type") == "tool_result":
                    tool_results += 1
                    if raw.get("toolDenialKind") == USER_REJECTED_DENIAL or _block_text(block).lstrip().startswith(REJECTION_MARKER):
                        rejections += 1
                    elif block.get("is_error") is True:
                        errors += 1
        else:
            return None
        interruption = any(text.lstrip().startswith(INTERRUPTION_MARKER) for text in texts)
        human = (
            not tool_results and not interruption and raw.get("isMeta") is not True and raw.get("isSidechain") is not True
            and raw.get("promptSource") != "system" and any(text.strip() and not _runtime_text(text) for text in texts)
        )
        return SessionEntry(session, at, branch, human, interruption and raw.get("isSidechain") is not True,
                            rejections, errors, None, (), _refs(texts))
    if kind == "assistant":
        usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
        values = tuple((name, _int(usage.get(name))) for name in CLAUDE_USAGE_FIELDS if _int(usage.get(name)) is not None)
        key = raw.get("requestId") or message.get("id")
        inputs = [
            json.dumps(block.get("input"), sort_keys=True) for block in content
            if isinstance(block, dict) and block.get("type") == "tool_use"
        ] if isinstance(content, list) else []
        return SessionEntry(session, at, branch, False, False, 0, 0, key if isinstance(key, str) else None, values, _refs(inputs))
    return None


class ClaudeTranscripts:
    """Counters-only reader of Claude Code's local session transcripts."""

    def __init__(self, projects_dir: Path | None, root: Path, config: dict[str, Any]) -> None:
        self.projects_dir = projects_dir
        self.root = root
        self.config = config
        self._parsed: list[tuple[list[SessionEntry], int]] | None = None
        self._reason: str | None = None

    def _directories(self) -> list[Path]:
        assert self.projects_dir is not None
        names = {_sanitize(str(self.root))}
        listing = run_git(["worktree", "list", "--porcelain"], cwd=self.root, check=False)
        if not listing.returncode:
            names.update(_sanitize(line[len("worktree "):].strip()) for line in listing.stdout.splitlines() if line.startswith("worktree "))
        worktrees = str((self.config.get("paths") or {}).get("worktrees", ".claude/worktrees"))
        prefix = _sanitize(str(self.root / worktrees)) + "-"
        return sorted(
            path for path in self.projects_dir.iterdir()
            if path.is_dir() and (path.name in names or path.name.startswith(prefix))
        )

    def parsed(self) -> tuple[list[tuple[list[SessionEntry], int]], str | None]:
        if self._parsed is not None:
            return self._parsed, self._reason
        self._parsed = []
        if self.projects_dir is None or not self.projects_dir.is_dir():
            self._reason = "source-missing"
            return self._parsed, self._reason
        try:
            directories = self._directories()
        except OSError:
            self._reason = "unreadable"
            return self._parsed, self._reason
        files = [file for directory in directories for file in [*sorted(directory.glob("*.jsonl")), *sorted(directory.glob("*/subagents/*.jsonl"))]]
        if not files:
            self._reason = "source-missing"
            return self._parsed, self._reason
        for file in files:
            entries: list[SessionEntry] = []
            unrecognized = 0
            try:
                handle = file.open(encoding="utf-8", errors="replace")
            except OSError:
                unrecognized += 1
                continue
            with handle:
                for line in handle:
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        unrecognized += 1
                        continue
                    if not isinstance(raw, dict):
                        unrecognized += 1
                        continue
                    if raw.get("type") not in ("user", "assistant"):
                        continue
                    entry = _parse_entry(raw)
                    if entry is None:
                        unrecognized += 1
                    else:
                        entries.append(entry)
            self._parsed.append((entries, unrecognized))
        if not any(entries for entries, _ in self._parsed) and any(count for _, count in self._parsed):
            self._reason = "unsupported-format"
        return self._parsed, self._reason

    def counters(self, *, requirement: str, children: list[str], branches: set[str]) -> dict[str, Any]:
        parsed, reason = self.parsed()
        if reason:
            return {"runtime": CLAUDE_RUNTIME, "status": UNKNOWN, "reason": reason}
        targets = {requirement, *children}
        backlog = requirement.split("#")[0] + "#"
        attributed: list[SessionEntry] = []
        by_branch = by_reference = unrecognized = 0
        shared = False
        for entries, bad in parsed:
            unrecognized += bad
            hits = [index for index, entry in enumerate(entries) if entry.refs & targets]
            first, last = (hits[0], hits[-1]) if hits else (-1, -2)
            for index, entry in enumerate(entries):
                in_span = first <= index <= last
                if in_span and any(ref.startswith(backlog) and ref not in targets for ref in entry.refs):
                    shared = True
                if entry.branch in branches:
                    by_branch += 1
                elif in_span:
                    by_reference += 1
                else:
                    continue
                attributed.append(entry)
        if not attributed:
            return {"runtime": CLAUDE_RUNTIME, "status": UNKNOWN, "reason": "no-attributed-sessions"}
        sessions = sorted({entry.session for entry in attributed})
        sources = [f"claude-transcript:{session}" for session in sessions]
        status_reason = "shared-session" if shared else None

        def value(number: float) -> dict[str, Any]:
            return partial(number, sources, status_reason) if status_reason else derived(number, sources)

        prompts = interruptions = rejections = errors = reprompts = 0
        session_time = active_time = 0.0
        usage: dict[str, tuple[tuple[str, int], ...]] = {}
        for session in sessions:
            ordered = sorted((entry for entry in attributed if entry.session == session), key=lambda entry: entry.at)
            pending = False
            for index, entry in enumerate(ordered):
                if entry.human_prompt:
                    prompts += 1
                    if pending:
                        reprompts += 1
                    pending = False
                if entry.interruption or entry.rejections:
                    pending = True
                interruptions += int(entry.interruption)
                rejections += entry.rejections
                errors += entry.errors
                if entry.usage:
                    usage[entry.usage_key or f"{session}:{index}"] = entry.usage
                if index:
                    active_time += min((entry.at - ordered[index - 1].at).total_seconds(), ACTIVE_GAP_CAP_SECONDS)
            session_time += (ordered[-1].at - ordered[0].at).total_seconds()
        fields = {
            name: value(sum(dict(values).get(name, 0) for values in usage.values()))
            if any(name in dict(values) for values in usage.values()) else unknown("runtime-unavailable", sources)
            for name in CLAUDE_USAGE_FIELDS
        }
        return {
            "runtime": CLAUDE_RUNTIME,
            "status": PARTIAL if shared else DERIVED,
            **({"reason": status_reason} if status_reason else {}),
            "attribution": {
                "method": "exact-child-branch-or-exact-reference-span",
                "child_branch_entries": by_branch,
                "reference_span_entries": by_reference,
                "sessions": sessions,
            },
            "prompt_turns": value(prompts),
            "interruptions": value(interruptions),
            "tool_rejections": value(rejections),
            "tool_errors": value(errors),
            "reprompts_after_interrupt_or_rejection": value(reprompts),
            "session_time_s": value(round(session_time, 3)),
            "active_time_s": value(round(active_time, 3)),
            "runtime_usage": {"runtime": CLAUDE_TRANSCRIPT_RUNTIME, "fields": fields},
            "unrecognized_entries": derived(unrecognized, sources),
        }


# Report assembly -----------------------------------------------------------


def _child_base(info: ChildInfo) -> dict[str, Any]:
    child_sources = info.sources or [f"gh:issue:{info.ref}"]
    issue = info.issue or {}
    reason = info.issue_reason or "source-missing"
    return {
        "ref": info.ref,
        "state": measured(issue.get("state"), child_sources) if info.issue else unknown(reason, child_sources),
        "created_at": measured(issue.get("created_at"), child_sources) if info.issue else unknown(reason, child_sources),
        "closed_at": measured(issue.get("closed_at"), child_sources, missing="open") if info.issue else unknown(reason, child_sources),
    }


def _unknown_child(ctx: Context, info: ChildInfo, why: str, events: list[dict[str, Any]] | None, friction_source: str) -> dict[str, Any]:
    """A child whose change identity or sources cannot be resolved: every section unknown with ``why``."""
    child_sources = info.sources or [f"gh:issue:{info.ref}"]
    return {
        **_child_base(info),
        "change": measured(info.change, child_sources) if info.change else unknown(why, child_sources),
        "managed": _managed(ctx, None, None, why),
        "routing": _routing(None, "", why),
        "execution_efficiency": {"runtime": None, "elapsed_ms": unknown(why, child_sources), "usage": {}},
        "verification": _verification(ctx, None, why),
        "validation": _validation(None, None, why, []),
        "review": _review(None, [], None, why)[0],
        "publication": _publication(ctx, None, None, why, {}),
        "ci": _ci(ctx, None, "", why)[0],
        "cycles_after_first_review": _cycles_after_first_review(None, {}, None, None),
        "friction": _friction_summary(_child_friction(events, info.ref, info.change), friction_source),
    }


def _target(ctx: Context, info: ChildInfo, provenance: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """The child's target repository; a malformed value makes only its remote sections unknown."""
    if info.target:
        return info.target, None
    value = (provenance or {}).get("target_repository")
    if value is None:
        return None, None
    try:
        return repo(str(value)), None
    except ManagedTaskError:
        ctx.note(f"child {info.ref}", "managed provenance target_repository is not owner/name")
        return None, "malformed-target-repository"


def _branch_ref(change: str, provenance: dict[str, Any] | None) -> str:
    """The child's branch: readable-identity decoration when committed provenance carries it."""
    import managed_work_identity
    try:
        return managed_work_identity.task_branch(change, (provenance or {}).get("work_identity"))
    except managed_work_identity.IdentityError:
        return f"agent/{change}"


def _branch_refs(change: str, provenance: dict[str, Any] | None) -> list[str]:
    """Every supported branch form; a resumed legacy child keeps its plain ``agent/<change>`` branch."""
    refs = [_branch_ref(change, provenance)]
    legacy = f"agent/{change}"
    if legacy not in refs:
        refs.append(legacy)
    return refs


def _published_branch(prs: list[dict[str, Any]] | None, branch_refs: list[str]) -> str:
    """The branch that actually carried publication, else the preferred form."""
    for pr in prs or []:
        ref = (pr.get("head") or {}).get("ref") if isinstance(pr.get("head"), dict) else None
        if ref in branch_refs:
            return ref
    return branch_refs[0]


def _child_report(ctx: Context, info: ChildInfo, events: list[dict[str, Any]] | None, friction_source: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(child section, runtime providers observed for it)``."""
    change = info.change
    child_sources = info.sources or [f"gh:issue:{info.ref}"]
    facts: dict[str, Any] = {"providers": set()}
    base = _child_base(info)
    if change is None:
        return _unknown_child(ctx, info, info.change_reason or "source-missing", events, friction_source), facts
    archive, provenance, state = _archive(ctx, change)
    branch_refs = _branch_refs(change, provenance)
    target, target_reason = _target(ctx, info, provenance)
    record, routing_source, routing_reason = _routing_record(ctx, change, info.ref)
    prs, pr_reason = _pull_requests(ctx, target, change, target_reason, branch_refs)

    history: History | None = None
    commit_counts: dict[int, int] = {}
    history_reason = pr_reason
    if prs is not None and target is not None:
        history, commit_counts = _history(ctx, target, change, prs)
    archived = _archive_versions(ctx, archive)
    archive_source = ctx.file_ref(archive / ".managed-task.json") if archive else None
    review_section, first_completed = _review(archive_source, archived, history, history_reason)
    validation = _validation(archive, history, history_reason, archived)
    ci, primary_runs = _ci(ctx, target, change, target_reason, branch_refs)
    routing = _routing(record, routing_source, routing_reason)
    section = {
        **base,
        "change": measured(change, child_sources),
        "branch": derived(_published_branch(prs, branch_refs), child_sources),
        "managed": _managed(ctx, archive, provenance, state),
        "routing": routing,
        "execution_efficiency": _execution_efficiency(record, routing_source, routing_reason),
        "verification": _verification(ctx, archive, state),
        "validation": validation,
        "review": review_section,
        "publication": _publication(ctx, target, prs, pr_reason, commit_counts),
        "ci": ci,
        "cycles_after_first_review": _cycles_after_first_review(first_completed, validation, primary_runs, ci["runs"].get("reason")),
        "friction": _friction_summary(_child_friction(events, info.ref, change, branch_refs), friction_source),
    }
    for provider in (routing["supervisor"]["provider"]["value"], routing["executor"]["provider"]["value"]):
        if isinstance(provider, str):
            facts["providers"].add(provider)
    for item in review_section["round_details"]:
        for perspective in item["perspectives"].values():
            if isinstance(perspective["provider"]["value"], str):
                facts["providers"].add(perspective["provider"]["value"])
    return section, facts


def _stage_value(values: list[dict[str, Any]], pick: Callable[..., Any]) -> dict[str, Any] | None:
    # A PR that was never merged or an Issue still open has no such stage; that is not missing evidence.
    values = [item for item in values if item.get("reason") not in ("not-merged", "open")]
    known = [(_time(item["value"]), item) for item in values if item["status"] != UNKNOWN and _time(item["value"])]
    if not known:
        return None
    chosen = pick(known, key=lambda pair: pair[0])[1]
    if len(known) < len(values):
        return partial(chosen["value"], chosen["sources"], "incomplete-inputs")
    return chosen


def _cycle(requirement: dict[str, Any], pre: dict[str, Any], children: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    sections = children
    rounds = [item for child in sections for item in child["review"]["round_details"]]
    perspectives = [p for item in rounds for p in item["perspectives"].values()]
    prs = [pr for child in sections for pr in child["publication"]["prs"]]
    candidates: dict[str, tuple[list[dict[str, Any]], Callable[..., Any]]] = {
        "requirement_created": ([requirement["created_at"]], min),
        "pre_authoring_started": ([pre["started_at"]], min),
        "depth_selected": ([pre["depth_selected_at"]], min),
        "handoff_prepared": ([pre["handoff_prepared_at"]], min),
        "child_created": ([child["created_at"] for child in sections], min),
        "child_imported": ([child["managed"]["imported_at"] for child in sections], min),
        "routed": ([child["routing"]["prepared_at"] for child in sections], min),
        "execution_recorded": ([child["routing"]["executor"]["recorded_at"] for child in sections], min),
        "first_review_launched": ([p["launched_at"] for p in perspectives], min),
        "last_review_completed": ([p["completed_at"] for p in perspectives], max),
        "pr_created": ([pr["created_at"] for pr in prs], min),
        "pr_merged": ([pr["merged_at"] for pr in prs], max),
        "child_closed": ([child["closed_at"] for child in sections], max),
        "requirement_closed": ([requirement["closed_at"]], max),
    }
    stages: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in STAGES:
        values, pick = candidates[name]
        value = _stage_value(values, pick)
        if value is None:
            missing.append(name)
        else:
            stages.append({"name": name, "at": value})
    # Durations follow the observed timeline; the sort is stable for equal timestamps.
    stages.sort(key=lambda stage: _time(stage["at"]["value"]))
    durations = [
        {"from": before["name"], "to": after["name"], "seconds": span(before["at"], after["at"])}
        for before, after in zip(stages, stages[1:])
    ]
    created, closed = requirement["created_at"], requirement["closed_at"]
    if closed["status"] != UNKNOWN:
        cycle_total = span(created, closed)
    elif created["status"] != UNKNOWN and closed.get("reason") == "open":
        cycle_total = lower_bound(span(created, derived(now.isoformat())), "open")
    else:
        cycle_total = unknown(closed.get("reason") or "source-missing", closed["sources"])
    return {"total_s": cycle_total, "stages": stages, "missing_stages": missing, "stage_durations": durations}


def _provider_usage(children: list[dict[str, Any]], session: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for child in children:
        efficiency = child["execution_efficiency"]
        if efficiency["runtime"]:
            bucket = groups.setdefault(f"executor/{efficiency['runtime']}", {})
            bucket.setdefault("elapsed_ms", []).append(efficiency["elapsed_ms"])
            for name, item in efficiency["usage"].items():
                bucket.setdefault(name, []).append(item)
        for item in child["review"]["round_details"]:
            for perspective in item["perspectives"].values():
                usage = perspective["runtime_usage"]
                runtime = usage["runtime"] or perspective["runtime"]["value"] or "unknown"
                bucket = groups.setdefault(f"reviewer/{runtime}", {})
                if usage["status"] != MEASURED:
                    bucket.setdefault("launches_without_usage", []).append(derived(1, perspective["runtime"]["sources"]))
                for name, field_value in usage["fields"].items():
                    bucket.setdefault(name, []).append(field_value)
    if session.get("status") in (DERIVED, PARTIAL):
        runtime_usage = session["runtime_usage"]
        groups[f"session/{runtime_usage['runtime']}"] = {name: [value] for name, value in runtime_usage["fields"].items()}
    return {key: {name: total(items) for name, items in sorted(bucket.items())} for key, bucket in sorted(groups.items())}


def build_report(ctx: Context, requirement_ref: str) -> dict[str, Any]:
    requirement = _canonical_ref(requirement_ref)
    if requirement is None:
        raise RequirementMetricsError("requirement must be owner/repo#N or https://github.com/owner/repo/issues/N")
    repository, number = issue_ref(requirement)
    issue: dict[str, Any] | None = None
    issue_source = [f"gh:issue:{requirement}"]
    if ctx.github is not None:
        try:
            payload = ctx.github.get(f"repos/{repository}/issues/{number}")
        except GitHubUnavailable as exc:
            raise RequirementMetricsError(
                f"cannot read Requirement {requirement}: {_bounded(str(exc))}; check gh auth and the reference, "
                "or rerun with --offline for the local-only view"
            ) from exc
        if not isinstance(payload, dict) or not payload.get("number"):
            raise RequirementMetricsError(f"cannot read Requirement {requirement}: unexpected GitHub payload")
        labels = {str(label.get("name", "")).lower() for label in payload.get("labels") or [] if isinstance(label, dict)}
        if REQUIREMENT_LABEL not in labels:
            raise RequirementMetricsError(f"{requirement} is not a {REQUIREMENT_LABEL} Issue; pass a Business Requirement")
        issue = payload
    requirement_section = {
        "ref": requirement,
        "title": measured(issue.get("title"), issue_source) if issue else unknown("offline", issue_source),
        "state": measured(issue.get("state"), issue_source) if issue else unknown("offline", issue_source),
        "created_at": measured(issue.get("created_at"), issue_source) if issue else unknown("offline", issue_source),
        "closed_at": measured(issue.get("closed_at"), issue_source, missing="open") if issue else unknown("offline", issue_source),
    }
    infos, children_count = _children(ctx, requirement, number, issue)
    requirement_section["children_count"] = children_count
    events, friction_source = _friction_events(ctx)
    retrospective, retrospective_source = _retrospective(ctx, number, requirement)
    child_sections: list[dict[str, Any]] = []
    providers: set[str] = set()
    child_event_ids: set[str] = set()
    for info in infos:
        try:
            section, facts = _child_report(ctx, info, events, friction_source)
        except Exception as exc:  # One child's unexpected source never aborts the report.
            ctx.note(f"child {info.ref}", f"{type(exc).__name__}: {exc}")
            section, facts = _unknown_child(ctx, info, "unreadable", events, friction_source), {"providers": set()}
        child_sections.append(section)
        providers.update(facts["providers"])
        child_event_ids.update(section["friction"]["ids"])
    pre = _pre_authoring(ctx, number)
    retrospective_ids = set((retrospective or {}).get("event_ids") or [])
    requirement_events = None if events is None else [
        event for event in events
        if _canonical_ref(event.get("task")) == requirement or event["id"] in retrospective_ids or event["id"] in child_event_ids
    ]
    friction = _friction_summary(requirement_events, friction_source)
    if retrospective_source:
        friction["count"]["sources"] = _source_list([*friction["count"]["sources"], retrospective_source])
    branches = {f"agent/{info.change}" for info in infos if info.change}
    branches.update(child["branch"]["value"] for child in child_sections if isinstance(child.get("branch"), dict) and child["branch"].get("value"))
    session = ctx.transcripts.counters(requirement=requirement, children=[info.ref for info in infos], branches=branches)
    session_quality: dict[str, Any] = {CLAUDE_RUNTIME: session}
    for provider in sorted(providers - {"claude"}):
        session_quality[provider] = {"runtime": provider, "status": UNKNOWN, "reason": "unsupported-runtime"}
    def children_total(path: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        """A sum over children is unknown when the child set is unknown, never zero."""
        if children_count["status"] == UNKNOWN:
            return unknown(children_count.get("reason") or "source-missing", children_count["sources"])
        value = total(path(child) for child in child_sections)
        if children_count["status"] in (MEASURED, DERIVED):
            return value
        return lower_bound(value, children_count.get("reason") or "incomplete-inputs")

    review_blockers = children_total(lambda child: child["review"]["dispositions"]["blocker"])
    project_blocked = unknown("no-recorded-history")
    human_stops = {
        "pre_authoring_decisions": pre["decisions_answered"],
        "review_blockers": review_blockers,
        "project_blocked": project_blocked,
        "session_interruptions": session.get("interruptions") or unknown(session.get("reason") or "source-missing"),
        "total": total([pre["decisions_answered"], review_blockers, project_blocked]),
    }

    causes = ("substantive-candidate-change", "reviewer-unavailable", "process-rerun", "unknown")
    totals = {
        "children": children_count,
        "executions": children_total(lambda child: child["routing"]["executions"]),
        "escalations": children_total(lambda child: child["routing"]["escalations"]["count"]),
        "review_rounds": children_total(lambda child: child["review"]["rounds"]),
        "review_launches": children_total(lambda child: child["review"]["launches"]),
        "review_wall_time_s": children_total(lambda child: child["review"]["wall_time_s"]),
        "review_findings_material": children_total(lambda child: child["review"]["findings"]["material"]),
        "review_findings_advisory": children_total(lambda child: child["review"]["findings"]["advisory"]),
        "review_reruns_by_cause": {cause: children_total(lambda child, cause=cause: child["review"]["reruns_by_cause"][cause]) for cause in causes},
        "validation_cycles": children_total(lambda child: child["validation"]["cycles"]),
        "full_validations": children_total(lambda child: child["validation"]["full_cycles"]),
        "validation_duration_s": children_total(lambda child: child["validation"]["total_duration_s"]),
        "ci_runs": children_total(lambda child: child["ci"]["runs"]),
        "ci_cycles": children_total(lambda child: child["ci"]["distinct_heads"]),
        "ci_failed_runs": children_total(lambda child: child["ci"]["failed_runs"]),
        "ci_wall_time_s": children_total(lambda child: child["ci"]["wall_time_total_s"]),
        "publication_cycles": children_total(lambda child: child["publication"]["publication_cycles"]),
        "publication_blocked_events": children_total(lambda child: child["publication"]["queue_blocked_events"]),
        "cycles_after_first_review": {
            "validation": children_total(lambda child: child["cycles_after_first_review"]["validation"]),
            "ci": children_total(lambda child: child["cycles_after_first_review"]["ci"]),
        },
        "human_stops": human_stops["total"],
        "friction": friction["count"],
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "head": _head(),
        "mode": "offline" if ctx.github is None else "online",
        "requirement": requirement_section,
        "cycle": _cycle(requirement_section, pre, child_sections, ctx.now),
        "pre_authoring": pre,
        "children": child_sections,
        "totals": totals,
        "human_stops": human_stops,
        "friction": friction,
        "session_quality": session_quality,
        "provider_usage": _provider_usage(child_sections, session),
        "diagnostics": ctx.diagnostics,
    }
    report["sources"] = sorted(_collect_sources(report))
    return report


def _head() -> str | None:
    try:
        result = run_git(["rev-parse", "HEAD"], cwd=current_worktree_root(), check=False)
    except Exception:
        return None
    return result.stdout.strip() or None if not result.returncode else None


def _collect_sources(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        sources = value.get("sources")
        if isinstance(sources, list) and "status" in value:
            found.update(item for item in sources if isinstance(item, str))
        for key, item in value.items():
            if key != "sources":
                found |= _collect_sources(item)
    elif isinstance(value, list):
        for item in value:
            found |= _collect_sources(item)
    return found


# Aggregate -----------------------------------------------------------------


ROW_METRICS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "cycle_time_s": lambda report: report["cycle"]["total_s"],
    "children": lambda report: report["totals"]["children"],
    "executions": lambda report: report["totals"]["executions"],
    "escalations": lambda report: report["totals"]["escalations"],
    "review_rounds": lambda report: report["totals"]["review_rounds"],
    "review_launches": lambda report: report["totals"]["review_launches"],
    "review_wall_time_s": lambda report: report["totals"]["review_wall_time_s"],
    "reruns_substantive": lambda report: report["totals"]["review_reruns_by_cause"]["substantive-candidate-change"],
    "reruns_reviewer_unavailable": lambda report: report["totals"]["review_reruns_by_cause"]["reviewer-unavailable"],
    "reruns_process": lambda report: report["totals"]["review_reruns_by_cause"]["process-rerun"],
    "full_validations": lambda report: report["totals"]["full_validations"],
    "ci_cycles": lambda report: report["totals"]["ci_cycles"],
    "ci_wall_time_s": lambda report: report["totals"]["ci_wall_time_s"],
    "publication_cycles": lambda report: report["totals"]["publication_cycles"],
    "human_stops": lambda report: report["totals"]["human_stops"],
    "friction": lambda report: report["totals"]["friction"],
}


def _min_observations() -> int:
    from model_routing import EFFICIENCY_MIN_PERCENTILE_OBSERVATIONS

    return EFFICIENCY_MIN_PERCENTILE_OBSERVATIONS


def _set_label(values: Iterable[Any]) -> str:
    known = sorted({str(value) for value in values if value is not None})
    return "+".join(known) if known else "unknown"


def _group_statistics(rows: list[dict[str, Any]], minimum: int) -> dict[str, Any]:
    if len(rows) < minimum:
        return {"n": len(rows), "adequacy": "insufficient", "minimum": minimum}
    metrics: dict[str, Any] = {}
    for name in ROW_METRICS:
        values = sorted(row["metrics"][name]["value"] for row in rows if row["metrics"][name]["status"] in (MEASURED, DERIVED))
        summary: dict[str, Any] = {"exact": len(values), "partial_or_unknown": len(rows) - len(values)}
        if len(values) >= minimum:
            summary["median"] = statistics.median(values)
            summary["p95"] = values[max(0, math.ceil(len(values) * 0.95) - 1)]
        else:
            summary["adequacy"] = "insufficient"
        metrics[name] = summary
    return {"n": len(rows), "adequacy": "adequate", "minimum": minimum, "metrics": metrics}


def aggregate(reports: list[dict[str, Any]], selection: dict[str, Any] | None = None,
              diagnostics: list[dict[str, str]] | None = None) -> dict[str, Any]:
    minimum = _min_observations()
    rows = []
    for report in reports:
        children = report["children"]
        rows.append({
            "requirement": report["requirement"]["ref"],
            "children_count": report["totals"]["children"]["value"],
            "task_family": _set_label(child["managed"]["task_family"]["value"] for child in children),
            "start_tier": _set_label(child["managed"]["start_tier"]["value"] for child in children),
            "metrics": {name: path(report) for name, path in ROW_METRICS.items()},
        })
    groups: dict[str, dict[str, Any]] = {}
    for dimension in ("children_count", "task_family", "start_tier"):
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            buckets.setdefault(str(row[dimension]), []).append(row)
        groups[dimension] = {
            key: {"requirements": [row["requirement"] for row in bucket], **_group_statistics(bucket, minimum)}
            for key, bucket in sorted(buckets.items())
        }
    runtime_groups: dict[str, dict[str, Any]] = {}
    for report in reports:
        for key, fields in report["provider_usage"].items():
            runtime_groups.setdefault(key, {})[report["requirement"]["ref"]] = fields
        for runtime, session in report["session_quality"].items():
            if session.get("status") in (DERIVED, PARTIAL):
                counters = {name: session[name] for name in (
                    "prompt_turns", "interruptions", "tool_rejections", "tool_errors",
                    "reprompts_after_interrupt_or_rejection", "session_time_s", "active_time_s",
                )}
                runtime_groups.setdefault(f"session-quality/{runtime}", {})[report["requirement"]["ref"]] = counters
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "head": _head(),
        "requirements": [row["requirement"] for row in rows],
        "selection": selection or {"method": "explicit", "requirements": derived(len(rows))},
        "rows": rows,
        "groups": groups,
        "runtime_groups": {key: {"n": len(value), "requirements": value} for key, value in sorted(runtime_groups.items())},
        "advice": ADVICE,
        "diagnostics": [*(diagnostics or []), *(item for report in reports for item in report["diagnostics"])],
    }


def closed_requirements(ctx: Context, since: str) -> tuple[list[str], dict[str, Any]]:
    """Closed Requirements since a date and the selection coverage (partial when the search was cut short)."""
    if ctx.github is None:
        raise RequirementMetricsError("--closed-since needs GitHub; pass explicit --requirement values with --offline")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        raise RequirementMetricsError("--closed-since must be YYYY-MM-DD")
    backlog = ctx.config.get("development_backlog")
    if not isinstance(backlog, dict) or not backlog.get("repository") or not backlog.get("project_label"):
        raise RequirementMetricsError("--closed-since needs [development_backlog] repository and project_label in .dev-platform.toml")
    query = (
        f"repo:{backlog['repository']} is:issue is:closed label:{REQUIREMENT_LABEL} "
        f"label:{backlog['project_label']} closed:>={since}"
    )
    items: list[Any] = []
    total_count: int | None = None
    incomplete = False
    for page in range(1, MAX_SEARCH_PAGES + 1):
        params = {"q": query, "per_page": 100, "page": page, "sort": "created", "order": "asc"}
        try:
            payload = ctx.github.get("search/issues?" + urllib.parse.urlencode(params))
        except GitHubUnavailable as exc:
            raise RequirementMetricsError(f"cannot list closed Requirements: {_bounded(str(exc))}") from exc
        batch = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(batch, list):
            raise RequirementMetricsError("cannot list closed Requirements: unexpected GitHub payload")
        total_count = _int(payload.get("total_count"))
        incomplete = incomplete or payload.get("incomplete_results") is True
        items.extend(batch)
        if len(batch) < 100 or (total_count is not None and len(items) >= total_count):
            break
    refs = sorted(
        {f"{repo(str(backlog['repository']))}#{item['number']}" for item in items if isinstance(item, dict) and isinstance(item.get("number"), int)},
        key=lambda ref: int(ref.split("#")[1]),
    )
    source = ["gh:search:issues"]
    if incomplete or total_count is None or total_count > len(items):
        reason = "search-incomplete" if incomplete else "search-truncated"
        ctx.note("closed-since selection", f"search listed {len(items)} of {total_count if total_count is not None else 'unknown'} closed Requirements")
        count = partial(len(refs), source, reason)
    else:
        count = derived(len(refs), source)
    return refs, {"method": "closed-since", "since": since, "requirements": count,
                  "total_count": measured(total_count, source, missing="unreadable")}


# Text output ---------------------------------------------------------------


def _fmt(item: dict[str, Any] | None) -> str:
    if not item:
        return "unknown"
    if item["status"] == UNKNOWN:
        return f"unknown ({item.get('reason', 'source-missing')})"
    value = item["value"]
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return f"{text} (partial: {item.get('reason')})" if item["status"] == PARTIAL else text


def render_report_text(report: dict[str, Any]) -> str:
    requirement = report["requirement"]
    totals = report["totals"]
    lines = [
        f"Requirement {requirement['ref']} [{report['mode']}] state={_fmt(requirement['state'])} "
        f"children={_fmt(requirement['children_count'])}",
        f"Cycle time (s): {_fmt(report['cycle']['total_s'])}",
        "Stages: " + (", ".join(f"{stage['name']}={stage['at']['value']}" for stage in report["cycle"]["stages"]) or "none"),
    ]
    if report["cycle"]["missing_stages"]:
        lines.append("Missing stages: " + ", ".join(report["cycle"]["missing_stages"]))
    for child in report["children"]:
        routing = child["routing"]
        review_section = child["review"]
        lines += [
            f"Child {child['ref']} change={_fmt(child['change'])} tier={_fmt(child['managed']['start_tier'])} "
            f"family={_fmt(child['managed']['task_family'])}",
            f"  routing: supervisor={_fmt(routing['supervisor']['provider'])}/{_fmt(routing['supervisor']['model'])} "
            f"executor={_fmt(routing['executor']['provider'])}/{_fmt(routing['executor']['model'])} "
            f"outcome={_fmt(routing['executor']['outcome'])} escalations={_fmt(routing['escalations']['count'])}",
            f"  verification: receipt={_fmt(child['verification']['receipt_present'])} passed={_fmt(child['verification']['passed'])}",
            f"  validation: cycles={_fmt(child['validation']['cycles'])} full={_fmt(child['validation']['full_cycles'])} "
            f"duration_s={_fmt(child['validation']['total_duration_s'])}",
            f"  review: rounds={_fmt(review_section['rounds'])} launches={_fmt(review_section['launches'])} "
            f"wall_s={_fmt(review_section['wall_time_s'])} material={_fmt(review_section['findings']['material'])} "
            "reruns=" + ", ".join(f"{cause}:{_fmt(value)}" for cause, value in review_section["reruns_by_cause"].items()),
            f"  publication: prs={_fmt(child['publication']['pr_count'])} cycles={_fmt(child['publication']['publication_cycles'])} "
            f"blocked={_fmt(child['publication']['queue_blocked_events'])}",
            f"  ci: runs={_fmt(child['ci']['runs'])} cycles={_fmt(child['ci']['distinct_heads'])} "
            f"failed={_fmt(child['ci']['failed_runs'])} wall_s={_fmt(child['ci']['wall_time_total_s'])}",
            f"  after first review: validation={_fmt(child['cycles_after_first_review']['validation'])} "
            f"ci={_fmt(child['cycles_after_first_review']['ci'])}",
            f"  friction: {_fmt(child['friction']['count'])}",
        ]
    lines.append("Totals: " + ", ".join(
        f"{name}={_fmt(value)}" for name, value in totals.items() if isinstance(value, dict) and "status" in value
    ))
    stops = report["human_stops"]
    lines.append("Human stops: " + ", ".join(f"{name}={_fmt(value)}" for name, value in stops.items()))
    for runtime, session in report["session_quality"].items():
        if session.get("status") == UNKNOWN:
            lines.append(f"Session ({runtime}): unknown ({session.get('reason')})")
        else:
            lines.append(
                f"Session ({runtime}): prompts={_fmt(session['prompt_turns'])} interruptions={_fmt(session['interruptions'])} "
                f"rejections={_fmt(session['tool_rejections'])} tool_errors={_fmt(session['tool_errors'])} "
                f"reprompts={_fmt(session['reprompts_after_interrupt_or_rejection'])} active_s={_fmt(session['active_time_s'])}"
            )
    for key, fields in report["provider_usage"].items():
        lines.append(f"Usage {key}: " + ", ".join(f"{name}={_fmt(value)}" for name, value in fields.items()))
    for item in report["diagnostics"]:
        lines.append(f"Diagnostic [{item['section']}]: {item['reason']}")
    return "\n".join(lines) + "\n"


def render_aggregate_text(result: dict[str, Any]) -> str:
    lines = [f"Requirements: {len(result['rows'])} (selection {result['selection']['method']}: "
             f"{_fmt(result['selection']['requirements'])})"]
    for row in result["rows"]:
        lines.append(
            f"{row['requirement']} family={row['task_family']} tier={row['start_tier']} "
            + " ".join(f"{name}={_fmt(value)}" for name, value in row["metrics"].items())
        )
    for dimension, buckets in result["groups"].items():
        for key, group in buckets.items():
            lines.append(f"Group {dimension}={key}: n={group['n']} adequacy={group['adequacy']}")
    for key, group in result["runtime_groups"].items():
        lines.append(f"Runtime group {key}: n={group['n']}")
    for item in result["diagnostics"]:
        lines.append(f"Diagnostic [{item['section']}]: {item['reason']}")
    lines.append(result["advice"])
    return "\n".join(lines) + "\n"


# CLI -----------------------------------------------------------------------


def make_context(root: Path, *, offline: bool, claude_projects_dir: Path | None, runner: GhRunner | None = None) -> Context:
    config = read_platform_config(root)
    github = None if offline else GitHub(runner or gh_runner(root))
    return Context(root=root, github=github, config=config, transcripts=ClaudeTranscripts(claude_projects_dir, root, config))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only end-to-end metrics for Business Requirements (advisory, no score).")
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=("json", "text"), default="json")
    common.add_argument("--offline", action="store_true", help="skip every remote read; remote sections are unknown")
    common.add_argument("--claude-projects-dir", type=Path, default=Path.home() / ".claude" / "projects")
    report_parser = sub.add_parser("report", parents=[common], help="report one Requirement")
    report_parser.add_argument("--requirement", required=True)
    aggregate_parser = sub.add_parser("aggregate", parents=[common], help="compare Requirements side by side")
    selection = aggregate_parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--requirement", action="append")
    selection.add_argument("--closed-since")
    args = parser.parse_args(argv)
    try:
        ctx = make_context(main_root(), offline=args.offline, claude_projects_dir=args.claude_projects_dir)
        if args.command == "report":
            report = build_report(ctx, args.requirement)
            output = render_report_text(report) if args.format == "text" else json.dumps(report, indent=2, sort_keys=True) + "\n"
        else:
            selection: dict[str, Any] | None = None
            if args.requirement:
                refs = args.requirement
            else:
                refs, selection = closed_requirements(ctx, args.closed_since)
            selection_diagnostics = list(ctx.diagnostics)
            reports = []
            for ref in dict.fromkeys(refs):
                ctx.diagnostics = []
                reports.append(build_report(ctx, ref))
            result = aggregate(reports, selection, selection_diagnostics)
            output = render_aggregate_text(result) if args.format == "text" else json.dumps(result, indent=2, sort_keys=True) + "\n"
    except (RequirementMetricsError, ManagedTaskError) as exc:
        print(f"requirement_metrics: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
