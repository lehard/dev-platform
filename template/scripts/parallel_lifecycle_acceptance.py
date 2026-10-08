#!/usr/bin/env python3
"""Offline, reproducible parallel-lifecycle acceptance scenario in a disposable sandbox.

Three candidates are admitted before any merge and driven through independent
review, a genuine repair, finalization, sequential integration with main
movement, an integration repair and the post-merge obligations. The coordinator
and worker code is the real code: only the external surfaces are local stand-ins,
namely a scripted ``gh`` executable (the local GitHub adapter, backed by a real
bare Git remote), a deterministic reviewer launcher, scripted writer commands and
a scripted archiver. Nothing here reaches a network or a real GitHub repository.

Run: ``python3 parallel_lifecycle_acceptance.py run --output <directory>``.
Exit status is nonzero when delivery is incomplete, a transition is unexpected,
containment fails or the execution bound is exhausted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any

from _platform_common import atomic_write_text

SCRIPTS = Path(__file__).resolve().parent
REPO = "acme/sandbox"
REQUIREMENT = "acme/backlog#353"
ARCHIVE_DATE = "2026-01-01"
CLOCK = "2026-01-01T00:00:00+0000"
MAX_ACTIONS = 400
DEADLINE_SECONDS = 240
IDENTITY = {"GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@localhost", "GIT_AUTHOR_DATE": CLOCK,
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@localhost", "GIT_COMMITTER_DATE": CLOCK}
CANDIDATES = (  # (letter, managed OpenSpec change, branch, source issue number)
    ("A", "change-a", "agent/br-353-t1-a", 11),
    ("B", "change-b", "agent/br-353-t2-b", 12),
    ("C", "change-c", "agent/br-353-t3-c", 13),  # conflicts with A: integration repair of a finalized managed change
)
SHARED = "".join(f"{name} = {index}\n" if name else "\n" for index, name in enumerate(
    ["VALUE", "", "", "", "", "", "", "", "", "OTHER"], 1))
CHECK = (
    "import ast, pathlib, sys\n"
    "root = pathlib.Path('.')\n"
    "for path in sorted(root.glob('*.py')):\n"
    "    text = path.read_text()\n"
    "    assert '<' * 7 not in text, path\n"
    "    ast.parse(text)\n"
    "assert 'BUG' not in (root / 'shared.py').read_text()\n"
)


class ScenarioError(RuntimeError):
    """The scenario did not deliver what the lifecycle promises."""


# ---- hermetic Git ------------------------------------------------------------------

def git(cwd: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, stdin=subprocess.DEVNULL,
                          check=False, timeout=60)
    if check and done.returncode:
        raise ScenarioError(f"git {' '.join(args)} failed in {cwd}: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout.strip()


def put(path: Path, text: str) -> None:
    atomic_write_text(path, text)


def commit_all(cwd: Path, message: str) -> str:
    git(cwd, "add", "-A")
    git(cwd, "commit", "-q", "-m", message)
    return git(cwd, "rev-parse", "HEAD")


def tree_digest(path: Path) -> str:
    """Content-and-mode digest of every file, ``.git`` included; the source must stay unchanged."""
    digest = hashlib.sha256()
    for current, directories, names in os.walk(path, followlinks=False):
        directories.sort()
        for name in sorted(names):
            file = Path(current) / name
            info = file.lstat()
            digest.update(f"{file.relative_to(path)}:{stat.S_IMODE(info.st_mode):o}:".encode())
            if stat.S_ISREG(info.st_mode):
                digest.update(file.read_bytes())
    return digest.hexdigest()


# ---- seed repository and candidate fixtures -----------------------------------------

SPEC = ("# {cap} Specification\n\n## Purpose\nFixture capability {cap} for the parallel lifecycle scenario.\n\n"
        "## Requirements\n\n### Requirement: {title}\n\nThe system SHALL provide {title}.\n\n"
        "#### Scenario: {title}\n- **WHEN** it runs\n- **THEN** it provides {title}\n")


def build_seed(seed: Path) -> None:
    seed.mkdir(parents=True)
    git(seed, "init", "-q", "-b", "main")
    git(seed, "config", "user.name", "Fixture")
    git(seed, "config", "user.email", "fixture@localhost")
    put(seed / ".dev-platform.toml", 'main_branch = "main"\n[independent_review]\nenabled = true\nprovider = "codex"\n')
    put(seed / "check.py", CHECK)
    put(seed / "shared.py", SHARED)
    put(seed / "openspec/config.yaml", "schema: spec-driven\n")
    put(seed / "openspec/specs/base/spec.md", SPEC.format(cap="base", title="Base behavior"))
    commit_all(seed, "Seed repository")


def candidate_files(letter: str, change: str | None, defect: bool) -> dict[str, str]:
    lower, cap = letter.lower(), f"cap-{letter.lower()}"
    issue = {"A": 11, "B": 12, "C": 13}[letter]
    value = '"BUG"' if defect else "1"
    files = {f"src_{lower}.py": f"VALUE_{letter} = {value}\n"}
    if change is None:
        return files
    root = f"openspec/changes/{change}/"
    return {**files,
        root + "proposal.md": f"## Why\nCandidate {letter} exercises the parallel lifecycle.\n\n## What Changes\n- Add src_{lower}.py\n",
        root + "design.md": f"Candidate {letter} adds one module and one shared constant.\n",
        root + "tasks.md": "- [x] implement\n",
        root + ".managed-task.json": json.dumps({"change": change, "source_issue": f"acme/backlog#{issue}"}),
        root + f"specs/{cap}/spec.md": "## ADDED Requirements\n\n" + (
            f"### Requirement: Candidate {letter} behavior\n\nThe system SHALL provide candidate {letter} behavior.\n\n"
            f"#### Scenario: Candidate {letter}\n- **WHEN** it runs\n- **THEN** it provides candidate {letter} behavior\n"),
        root + "verification.md": "OpenSpec-Verify: PASS\nVerification-Method: fixture\n",
        root + "automated-checks.json": '{"outcome":"success"}\n',
    }


def author_candidate(author: Path, letter: str, change: str | None, branch: str, defect: bool) -> str:
    """One candidate from the shared base; A and C edit the same line, B a distant one of the same file."""
    git(author, "checkout", "-q", "-B", branch, "origin/main")
    for path, text in candidate_files(letter, change, defect).items():
        put(author / path, text)
    lines = (author / "shared.py").read_text().splitlines(keepends=True)
    if letter == "B":
        lines[9] = "OTHER = 'b'\n"
    else:
        lines[0] = f"VALUE = {'2' if letter == 'A' else '3'}  # {letter.lower()}\n"
    put(author / "shared.py", "".join(lines))
    head = commit_all(author, f"Candidate {letter}")
    git(author, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    return head


# ---- the local GitHub adapter ---------------------------------------------------------

def read_ref(remote: Path, name: str) -> str | None:
    """Resolve a ref of the bare remote without spawning Git (loose ref first, then packed-refs)."""
    loose = remote / name
    if loose.is_file():
        return loose.read_text().strip()
    packed = remote / "packed-refs"
    if packed.is_file():
        for line in packed.read_text().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == name and not line.startswith("#"):
                return parts[0]
    return None


class LocalGitHub:
    """Strict stand-in for the ``gh`` CLI surface the lifecycle uses, backed by a real bare Git remote.

    PR heads are observed from Git refs; ``update-branch`` and the protected squash merge really
    merge in Git. Stale expected heads, checks for another head and unsupported calls fail instead
    of returning generic success.
    """

    def __init__(self, remote: Path, repo: str):
        self.remote, self.repo = remote, repo
        self.prs: dict[str, dict] = {}
        self.comments: dict[str, list[dict]] = {}
        self.calls: list[dict] = []
        self.checks: dict[str, bool] = {}
        self.next_id = 0
        self.actor = "automation"  # who is acting: automation, developer or operator
        self.operator_actions: list[dict] = []

    # -- PR model --
    def add_pr(self, number: int, branch: str) -> None:
        self.prs[str(number)] = {"branch": branch, "labels": [], "merged": False}
        self.comments[str(number)] = []

    def head(self, number: str) -> str:
        head = read_ref(self.remote, "refs/heads/" + self.prs[number]["branch"])
        if head is None:
            raise ScenarioError(f"PR #{number} branch is missing from the remote")
        pull = f"refs/pull/{number}/head"
        if read_ref(self.remote, pull) != head:  # GitHub maintains pull/N/head for every PR head
            git(self.remote, "update-ref", pull, head)
        return head

    def pr_json(self, number: str) -> dict:
        pr = self.prs[number]
        return {"number": int(number), "state": "closed" if pr["merged"] else "open", "merged": pr["merged"],
                "merged_at": "2026-01-01T00:00:00Z" if pr["merged"] else None, "base": {"ref": "main"},
                "head": {"sha": self.head(number), "ref": pr["branch"]},
                "labels": [{"name": name} for name in pr["labels"]]}

    def checks_pass(self, head: str) -> bool:
        if head not in self.checks:
            with tempfile.TemporaryDirectory(prefix="gh-check-") as work:
                archive = subprocess.run(["git", "archive", head], cwd=self.remote, capture_output=True, check=True,
                                         stdin=subprocess.DEVNULL)
                subprocess.run(["tar", "-x", "-C", work], input=archive.stdout, check=True, capture_output=True)
                done = subprocess.run([sys.executable, "check.py"], cwd=work, capture_output=True, check=False,
                                      stdin=subprocess.DEVNULL, timeout=60)
            self.checks[head] = done.returncode == 0
        return self.checks[head]

    def clone(self, work: str) -> Path:
        path = Path(work) / "clone"
        git(Path(work), "clone", "-q", str(self.remote), str(path))
        git(path, "config", "user.name", "GitHub")
        git(path, "config", "user.email", "github@localhost")
        return path

    # -- ``gh`` entrypoint --
    def run(self, argv: list[str]) -> tuple[int, str, str]:
        entry: dict[str, Any] = {"seq": len(self.calls) + 1, "argv": [a[:60] for a in argv]}
        try:
            code, out, err = self.dispatch(argv, entry)
        except KeyError as exc:
            code, out, err = 1, "", f"HTTP 404: not found: {exc}"
        if entry.get("unsupported"):
            code = 2
        if entry.get("mutation") and self.actor == "operator":  # a manual completion action, observed at the adapter
            self.operator_actions.append({"call": entry["argv"][:3], "mutation": entry["mutation"]})
        self.calls.append(entry)
        return code, out, err

    def unsupported(self, argv: list[str], entry: dict) -> tuple[int, str, str]:
        entry["unsupported"] = True
        return 2, "", "unsupported fake gh call: gh " + " ".join(argv)

    def dispatch(self, argv: list[str], entry: dict) -> tuple[int, str, str]:
        if argv[:3] == ["repo", "view", "--json"]:
            return 0, json.dumps({"nameWithOwner": self.repo}), ""
        if argv[:2] == ["label", "create"]:
            return 0, "", ""
        if argv[:2] == ["pr", "list"]:
            label = argv[argv.index("--label") + 1] if "--label" in argv else None
            rows = [{"number": int(n), "labels": [{"name": x} for x in pr["labels"]]} for n, pr in self.prs.items()
                    if label is None or label in pr["labels"]]
            return 0, json.dumps(rows), ""
        if argv[:2] == ["pr", "view"]:
            data = self.pr_json(argv[2])
            if argv[3:] == ["--json", "baseRefName"]:
                return 0, json.dumps({"baseRefName": data["base"]["ref"]}), ""
            return 0, json.dumps({"state": data["state"].upper(), "headRefOid": data["head"]["sha"]}), ""
        if argv[:2] == ["pr", "checks"]:
            ok = self.checks_pass(self.head(argv[2]))
            rows = [{"name": "fixture-check", "state": "SUCCESS" if ok else "FAILURE", "workflow": "ci",
                     "link": "local://fixture-check"}]
            # Real ``gh pr checks --json`` exits 0 for passed, pending and failed lists.
            return 0, json.dumps(rows), ""
        if argv[:2] == ["pr", "merge"]:
            return self.merge(argv, entry)
        if argv[:1] == ["api"]:
            return self.api(argv, entry)
        return self.unsupported(argv, entry)

    def merge(self, argv: list[str], entry: dict) -> tuple[int, str, str]:
        number, head = argv[2], argv[argv.index("--match-head-commit") + 1]
        if "--squash" not in argv or self.prs[number]["merged"]:
            return 1, "", "merge refused: only squash merges of open PRs are supported"
        if self.head(number) != head:
            return 1, "", "Head branch was modified. Review the changes and try again."
        if not self.checks_pass(head):
            return 1, "", "Required status checks have not passed"
        if subprocess.run(["git", "merge-base", "--is-ancestor", "refs/heads/main", head], cwd=self.remote,
                          stdin=subprocess.DEVNULL, capture_output=True, check=False).returncode:
            return 1, "", "Base branch was modified. Update the branch and try again."
        with tempfile.TemporaryDirectory(prefix="gh-merge-") as work:
            path = self.clone(work)
            git(path, "merge", "--squash", "-q", head)
            git(path, "commit", "-q", "-m", f"Merge PR #{number} ({self.prs[number]['branch']})")
            git(path, "push", "-q", "origin", "HEAD:refs/heads/main")
        self.prs[number]["merged"] = True
        entry.update(mutation="merge", number=int(number), head=head)
        return 0, "", ""

    def api(self, argv: list[str], entry: dict) -> tuple[int, str, str]:
        method, fields, endpoint, items, slurp = "GET", {}, None, argv[1:], False
        while items:
            item = items.pop(0)
            if item == "-X":
                method = items.pop(0)
            elif item == "-f":
                key, _, value = items.pop(0).partition("=")
                fields[key] = value
            elif item == "--paginate":
                continue
            elif item == "--slurp":
                slurp = True
            elif endpoint is None:
                endpoint = item
            else:
                return self.unsupported(argv, entry)
        if fields and method == "GET":
            method = "POST"  # ``gh api`` with -f fields posts, like the real CLI
        path, _, query = (endpoint or "").partition("?")
        prefix = f"repos/{self.repo}/"
        if not path.startswith(prefix):
            return self.unsupported(argv, entry)
        path = path[len(prefix):]
        match = re.fullmatch(r"pulls/(\d+)", path)
        if match and method == "GET":
            return 0, json.dumps(self.pr_json(match.group(1))), ""
        if path == "pulls" and method == "GET":
            wanted = urllib.parse.parse_qs(query).get("state", ["open"])[0]
            rows = [self.pr_json(n) for n, pr in self.prs.items() if pr["merged"] == (wanted == "closed")]
            return 0, json.dumps(rows), ""
        match = re.fullmatch(r"issues/(\d+)/comments", path)
        if match and match.group(1) in self.prs:
            number = match.group(1)
            if method == "GET":
                # Real ``gh api --paginate --slurp`` returns one array per page.
                rows = [self.comments[number]] if slurp else self.comments[number]
                return 0, json.dumps(rows), ""
            if method == "POST":
                self.next_id += 1
                self.comments[number].append({
                    "id": self.next_id, "author_association": "OWNER", "user": {"login": "coordinator"},
                    "created_at": "2026-01-01T00:00:00Z", "body": fields["body"]})
                entry.update(mutation="comment", number=int(number))
                return 0, json.dumps({"id": self.next_id}), ""
        match = re.fullmatch(r"issues/(\d+)/labels(?:/(.+))?", path)
        if match and match.group(1) in self.prs:
            labels = self.prs[match.group(1)]["labels"]
            if method == "POST":
                if fields.get("labels[]") not in labels:
                    labels.append(fields["labels[]"])
                entry.update(mutation="label")
                return 0, "[]", ""
            if method == "DELETE" and match.group(2):
                name = urllib.parse.unquote(match.group(2))
                if name not in labels:
                    return 1, "", "HTTP 404: Label does not exist"
                labels.remove(name)
                entry.update(mutation="label")
                return 0, "", ""
        match = re.fullmatch(r"compare/([0-9a-f]{40})\.\.\.([0-9a-f]{40})", path)
        if match and method == "GET":
            names = git(self.remote, "diff", "--name-only", f"{match.group(1)}...{match.group(2)}").splitlines()
            return 0, json.dumps({"files": [{"filename": name} for name in names]}), ""
        match = re.fullmatch(r"pulls/(\d+)/update-branch", path)
        if match and method == "PUT" and match.group(1) in self.prs:
            number = match.group(1)
            if fields.get("expected_head_sha") != self.head(number):
                return 1, "", "HTTP 422: expected head sha didn't match current head ref"
            branch = self.prs[number]["branch"]
            with tempfile.TemporaryDirectory(prefix="gh-update-") as work:
                clone = self.clone(work)
                git(clone, "checkout", "-q", "-B", branch, f"origin/{branch}")
                merged = subprocess.run(["git", "merge", "--no-edit", "-q", "origin/main"], cwd=clone,
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
                if merged.returncode:
                    return 1, "", "HTTP 422: merge conflict between base and head"
                git(clone, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
            entry.update(mutation="update-branch", number=int(number))
            return 0, "{}", ""
        return self.unsupported(argv, entry)


# ---- scripted external behaviours --------------------------------------------------

REPAIR_WRITER = (
    "import pathlib, subprocess\n"
    "for path in pathlib.Path('.').glob('src_*.py'):\n"
    "    text = path.read_text()\n"
    "    if 'BUG' in text:\n"
    "        path.write_text(text.replace('\"BUG\"', '1'))\n"
    "        subprocess.run(['git', 'add', str(path)], check=True, stdin=subprocess.DEVNULL)\n"
    "        subprocess.run(['git', '-c', 'user.name=Repair', '-c', 'user.email=repair@localhost', 'commit', '-q',\n"
    "                        '-m', 'Repair reviewed defect'], check=True, stdin=subprocess.DEVNULL)\n"
)
INTEGRATION_WRITER = (
    "import pathlib, re\n"
    "path = pathlib.Path('shared.py')\n"
    "text = path.read_text()\n"
    "text = re.sub(r'<<<<<<<[^\\n]*\\n.*?=======\\n.*?>>>>>>>[^\\n]*\\n', 'VALUE = 5  # a+c\\n', text, flags=re.S)\n"
    "path.write_text(text)\n"
)


def archiver(checkout: Path, change: str, env: dict) -> None:
    """Scripted stand-in for the trusted archive entrypoint: archive move plus own spec materialization."""
    source = checkout / "openspec/changes" / change
    target = checkout / "openspec/changes/archive" / f"{ARCHIVE_DATE}-{change}"
    target.parent.mkdir(parents=True, exist_ok=True)
    git(checkout, "mv", str(source.relative_to(checkout)), str(target.relative_to(checkout)))
    for spec in sorted((target / "specs").glob("*/spec.md")):
        title = f"Candidate {change[-1].upper()} behavior"
        put(checkout / "openspec/specs" / spec.parent.name / "spec.md", SPEC.format(cap=spec.parent.name, title=title))


def checks_runner(checkout: Path, env: dict) -> None:
    done = subprocess.run([sys.executable, "check.py"], cwd=checkout, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, check=False, timeout=60)
    if done.returncode:
        raise ScenarioError("selected fixture check failed: " + done.stderr[-300:])


# ---- the scenario ------------------------------------------------------------------

def post_merge_problems(transitions: list[list]) -> list[str]:
    """Every merged candidate needs a completed result for each post-merge obligation."""
    results = {(e[0], e[2].split(":")[0]): e[4] for e in transitions if e[1] == "result"}
    problems = []
    for letter in ("A", "B", "C"):
        for kind in ("retrospective", "terminal-reconciliation", "cleanup"):
            outcome = results.get((letter, kind))
            if outcome is None or outcome.startswith(("blocked", "failed")):
                problems.append(f"post-merge job {kind} for {letter} did not complete ({outcome})")
    if results.get(("C", "terminal-reconciliation")) != "requirement-reconciled":
        problems.append("the last merged child did not reconcile the Requirement")
    return problems


def structure_problems(summary: dict) -> list[str]:
    """Structured checks over the recorded lifecycle; each names what the delivery lacks."""
    problems = []
    events = summary["transitions"]
    reached = {tuple(e[:3]) for e in events if e[1] == "record"}
    results = [(e[0], e[2].split(":")[0], e[4]) for e in events if e[1] == "result"]
    claims = [(e[0], e[2].split(":")[0]) for e in events if e[1] == "claim"]
    if summary["unsupported_gh_calls"]:
        problems.append(f"unsupported GitHub calls: {summary['unsupported_gh_calls']}")
    if not all(summary["merged"].values()) or set(summary["merged"]) != {"A", "B", "C"}:
        problems.append(f"not every candidate merged: {summary['merged']}")
    if set(summary["states_before_first_merge"].values()) != {"ready"}:
        problems.append(f"candidates were not all ready before the first merge: {summary['states_before_first_merge']}")
    for needed in (("B", "record", "repair-pending"), ("B", "record", "finalize-pending"),
                   ("C", "record", "integration-repair-pending"), ("A", "record", "merged"),
                   ("B", "record", "merged"), ("C", "record", "merged")):
        if needed not in reached:
            problems.append(f"lifecycle never recorded {needed[2]} for {needed[0]}")
    if ("B", "repair", "pushed") not in results:
        problems.append("no review repair was pushed for B")
    if ("C", "integration-repair", "validated-push") not in results:
        problems.append("no integration repair was pushed for C")
    if claims.count(("B", "review")) < 2 or claims.count(("C", "review")) < 2:
        problems.append("repaired candidates were not reviewed again")
    if claims.count(("C", "finalize")) < 2:
        problems.append("the integration-repaired candidate did not return through finalization")
    if ["B", "update-branch"] not in summary["merge_operations"]:
        problems.append("main movement never updated candidate B")
    if [m for m in summary["merge_operations"] if m[1] == "merge"] != [["A", "merge"], ["B", "merge"], ["C", "merge"]]:
        problems.append(f"merges were not sequential A, B, C: {summary['merge_operations']}")
    if summary["operator_actions"]:
        problems.append(f"operator completion actions were required: {summary['operator_actions']}")
    return problems


class Scenario:
    def __init__(self, output: Path, *, max_actions: int = MAX_ACTIONS):
        self.output = output.resolve()
        self.max_actions = max_actions
        self.actions = 0
        self.developer_actions: list[dict] = []
        self.workers = 0
        self.llm_calls: list[list[str]] = []
        self.closed: set[str] = set()
        self.checkpointed = False

    # -- setup --
    def setup(self) -> None:
        out = self.output
        if out.exists() and any(out.iterdir()):
            raise ScenarioError(f"output directory is not empty: {out}")
        out.mkdir(parents=True, exist_ok=True)
        self.sandbox = out / "sandbox"
        self.work = out / "work"
        for directory in (self.sandbox, self.work, out / "home"):
            directory.mkdir(parents=True, exist_ok=True)
        self.seed = out / "seed"
        env = {key: value for key, value in os.environ.items()
               if not re.search(r"^(GH|GITHUB)_|TOKEN|SECRET|^(GIT|SSH)_ASKPASS$|^SSH_AUTH_SOCK$", key)}
        env.update(IDENTITY, HOME=str(out / "home"), XDG_CONFIG_HOME=str(out / "home/.config"),
                   XDG_DATA_HOME=str(out / "home/.local"), XDG_CACHE_HOME=str(out / "home/.cache"),
                   GH_CONFIG_DIR=str(out / "home/gh-disabled"), GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file",
                   PYTHONDONTWRITEBYTECODE="1")
        os.environ.clear()
        os.environ.update(env)
        build_seed(self.seed)
        self.seed_digest = tree_digest(self.seed)
        self.remote = out / "remote.git"
        git(out, "clone", "-q", "--bare", str(self.seed), str(self.remote))
        sys.path.insert(0, str(SCRIPTS))
        import disposable_repository_sandbox as sandbox

        self.sandbox_module = sandbox
        self.sandboxes = ("coordinator", "author")
        for name in self.sandboxes:
            path = sandbox.create(str(self.seed), str(self.sandbox), name)
            git(path, "remote", "set-url", "origin", str(self.remote))
            exclude = path / ".git/info/exclude"  # the ownership marker is not candidate content
            put(exclude, exclude.read_text() + f"\n{sandbox.MARKER}\n")
            git(path, "fetch", "-q", "origin")
        self.root = self.sandbox / "coordinator"
        self.author = self.sandbox / "author"
        self.github = LocalGitHub(self.remote, REPO)
        real_run = subprocess.run

        def routed(command, *args, **kwargs):
            """Every ``gh`` invocation is answered by the local adapter; everything else is real."""
            if isinstance(command, (list, tuple)) and command and command[0] == "gh":
                code, out_text, err_text = self.github.run([str(part) for part in command[1:]])
                text = kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding")
                done = subprocess.CompletedProcess(command, code, out_text if text else out_text.encode(),
                                                   err_text if text else err_text.encode())
                if kwargs.get("check") and code:
                    raise subprocess.CalledProcessError(code, command, done.stdout, done.stderr)
                return done
            return real_run(command, *args, **kwargs)

        subprocess.run = routed
        os.chdir(self.root)

    def tick(self) -> None:
        self.actions += 1
        if self.actions > self.max_actions:
            raise ScenarioError(f"execution bound exhausted after {self.max_actions} actions")

    def remote_head(self, branch: str) -> str:
        return git(self.remote, "rev-parse", f"refs/heads/{branch}")

    def modules(self) -> None:
        import candidate_lifecycle, integration_contour, lifecycle_workers, post_review_finalization
        import pr_review_gate, publication_queue, independent_review_runner

        self.lifecycle, self.contour, self.workers_module = candidate_lifecycle, integration_contour, lifecycle_workers
        self.final, self.gate, self.queue, self.reviewer = (post_review_finalization, pr_review_gate,
                                                            publication_queue, independent_review_runner)
        self.reviewer.resolve_binary = lambda *a, **k: ("fake-codex", None)

    # -- candidate admission by the (scripted) developer --
    def admit_all(self) -> None:
        self.numbers: dict[str, int] = {}
        for index, (letter, change, branch, _) in enumerate(CANDIDATES, 1):
            head = author_candidate(self.author, letter, change, branch, defect=letter == "B")
            self.github.add_pr(index, branch)
            self.numbers[letter] = index
            if change is None:  # quick task: plain admission, no developer handoff and no managed gates
                self.queue.admit(self.root, index, head)
            else:
                identity = self.gate.task_identity(self.author, change)
                root = self.author / "openspec/changes" / change
                gates = {name: {"result": "passed", "identity": identity,
                                "evidence": self.gate.file_reference(self.author, root / file)}
                         for name, file in (("selected-checks", "automated-checks.json"),
                                            ("semantic-verification", "verification.md"))}
                gates["developer-friction"] = {"result": "passed", "identity": identity, "evidence": {"head": head}}
                self.queue.admit(self.root, index, head, handoff={"task_identity": identity, "gates": gates})
            self.tick()

    # -- workers --
    def candidates(self) -> list[dict]:
        return [self.queue.candidate_status(self.root, n, repo=REPO) for n in sorted(self.numbers.values())]

    def trust(self) -> dict:
        return {"trusted_apps": self.queue.trusted_apps(self.root),
                "trusted_writers": lambda comments: self.queue.trusted_writers(
                    self.root, comments, (self.workers_module.CLAIM_PREFIX,), repo=REPO)}

    def gh_json(self, *args: str) -> Any:
        return self.workers_module._gh_json(*args)

    def work_once(self, kinds: frozenset[str]) -> dict | None:
        """One real ``work_next`` claim followed by the real executor for the claimed job."""
        w = self.workers_module
        self.workers += 1
        worker = f"worker-{self.workers}"

        def list_prs() -> list[dict]:
            listed = self.gh_json("api", "--paginate", f"repos/{REPO}/pulls?state=open&per_page=100")
            if kinds & (w.POST_MERGE_KINDS | {"contribution-integration"}):
                closed = self.gh_json("api", f"repos/{REPO}/pulls?state=closed&sort=updated&direction=desc&per_page=50")
                listed = [*listed, *({**pr, "merged": True} for pr in closed if pr.get("merged_at"))]
            return listed

        def comments_for(number: int) -> list[dict]:
            return self.gh_json("api", "--paginate", f"repos/{REPO}/issues/{number}/comments?per_page=100")

        def post_comment(number: int, body: str) -> None:
            self.gh_json("api", f"repos/{REPO}/issues/{number}/comments", "-f", f"body={body}")

        def pr_head(number: int) -> str:
            return self.gh_json("api", f"repos/{REPO}/pulls/{number}")["head"]["sha"]

        result = w.work_next(kinds, list_prs=list_prs, comments_for=comments_for, post_comment=post_comment,
                             worker=worker, current_head=pr_head, **self.trust())
        self.tick()
        if result["status"] == "idle":
            return None
        if result["status"] != "claimed":
            raise ScenarioError(f"unexpected claim status {result['status']}")
        job = result["job"]
        number = job["number"]
        branch = self.github.prs[str(number)]["branch"]
        source = self.remote.as_uri()
        candidate = self.queue.candidate_status(self.root, number, repo=REPO)
        post = lambda body: post_comment(number, body)  # noqa: E731
        current = lambda: self.remote_head(branch)  # noqa: E731
        workdir = tempfile.mkdtemp(prefix=f"job-{number}-{job['kind']}-", dir=self.work)
        kind = job["kind"]
        if kind in {"review", "repair"}:
            self.llm_calls.append([kind, str(number)])
            outcome = self.gate.run_claimed(
                self.root, REPO, candidate, job, source_repo=source, branch=branch, allowed_paths=["src_a.py", "src_b.py", "src_c.py"],
                llm_command=[sys.executable, "-c", REPAIR_WRITER], current_head=current, post_result=post,
                workdir=workdir, launcher=self.launcher(), worker=worker)
        elif kind == "finalize":
            outcome = self.final.run_claimed_finalize(
                self.root, REPO, candidate, job, source_repo=source, branch=branch, current_head=current,
                post_result=post, workdir=workdir, archiver=archiver, checks_runner=checks_runner, worker=worker)
        elif kind == "integration-repair":
            outcome = self.contour.run_claimed_integration_repair(
                self.root, REPO, candidate, job, source_repo=source, branch=branch, allowed_paths=[],
                llm_command=[sys.executable, "-c", INTEGRATION_WRITER], current_head=current, post_result=post,
                workdir=workdir, worker=worker)
        elif kind in w.POST_MERGE_KINDS:
            outcome = self.contour.run_claimed_post_merge(
                self.root, REPO, candidate, job, branch=branch, post_result=post, ops=self.ops(), worker=worker)
        else:
            raise ScenarioError(f"unexpected job kind {kind}")
        if outcome.get("status") in {"discarded", "failed", "rejected", "blocked-escalation", "blocked"}:
            raise ScenarioError(f"{kind} job for PR #{number} ended {outcome}")
        return {"job": job, "outcome": outcome}

    def launcher(self):
        reviewer = self.reviewer
        calls = self.llm_calls

        def launch(argv, cwd, timeout):
            if argv[-1] == reviewer.PREFLIGHT_PROMPT:
                return reviewer.LaunchResult(0, '{"type":"thread.started","thread_id":"probe"}')
            findings = []
            for source in sorted(Path(cwd).glob("src_*.py")):
                if "BUG" in source.read_text():
                    findings.append({"id": f"defect-{source.stem}", "severity": "material",
                                     "summary": f"{source.name} keeps a placeholder defect value",
                                     "evidence": f"{source.name}:1 assigns the literal BUG"})
            calls.append(["reviewer-context"])
            put(Path(argv[argv.index("--output-last-message") + 1]), json.dumps({"findings": findings}))
            return reviewer.LaunchResult(0, json.dumps({"type": "thread.started", "thread_id": f"ctx-{len(calls)}"}))
        return launch

    def ops(self):
        contour, scenario = self.contour, self
        by_branch = {branch: (f"acme/backlog#{issue}") for _, _, branch, issue in CANDIDATES}

        class Ops(contour.LifecycleOps):
            def lineage(self, root, branch):
                return {"requirement": REQUIREMENT, "child": by_branch[branch]}

            def children(self, root, requirement):
                return sorted(by_branch.values())

            def child_closed(self, root, child):
                return child in scenario.closed

            def reconcile_child(self, root, child):
                scenario.closed.add(child)

            def requirement_checkpoint(self, root, requirement, event_ids):
                scenario.checkpointed = True

            def requirement_checkpointed(self, root, requirement):
                return scenario.checkpointed

            def reconcile_parent(self, root, requirement, merged_children):
                scenario.parent_reconciled = True

        return Ops()

    def drain(self, kinds: frozenset[str]) -> int:
        done = 0
        while self.work_once(kinds) is not None:
            done += 1
        return done

    # -- the developer's content-bound semantic handoff after any repair --
    def developer_handoff(self) -> int:
        count = 0
        for candidate in self.candidates():
            red = candidate.get("red_gate") or {}
            if candidate["state"] != "blocked-retryable" or red.get("name") != "semantic-verification":
                continue
            number, head = candidate["number"], candidate["head"]
            identity = candidate["task_identity"]
            branch = self.github.prs[str(number)]["branch"]
            change = identity["change"]
            checkout = self.work / f"developer-{number}-{head[:8]}"
            git(self.work, "clone", "-q", "--no-checkout", str(self.remote), str(checkout))
            git(checkout, "checkout", "-q", "--detach", head)
            base = checkout / "openspec/changes" / change
            if not base.is_dir():
                matches = sorted((checkout / "openspec/changes/archive").glob(f"*-{change}"))
                base = matches[0]
            gates = {name: {"result": "passed", "identity": identity,
                            "evidence": self.gate.file_reference(checkout, base / file)}
                     for name, file in (("selected-checks", "automated-checks.json"),
                                        ("semantic-verification", "verification.md"))}
            self.github.actor = "developer"
            try:
                self.queue._transition(self.root, REPO, number, "finalize-pending", head, task_identity=identity,
                                       inherit_identity=False, gates=gates)
                self.queue.publish_job(self.root, REPO, number, "finalize", head, task_identity=identity,
                                       attempt=candidate.get("attempts", {}).get("finalize", 0) + 1)
            finally:
                self.github.actor = "automation"
            self.developer_actions.append({"action": "semantic-verification-handoff", "candidate": branch})
            self.tick()
            count += 1
        return count

    def settle(self) -> None:
        w = self.workers_module
        order = (frozenset({"review"}), frozenset({"repair"}), frozenset({"integration-repair"}), frozenset({"finalize"}))
        while True:
            progressed = 0
            for kinds in order:
                progressed += self.drain(kinds)
            progressed += self.developer_handoff()
            progressed += self.drain(frozenset(w.POST_MERGE_KINDS))
            if not progressed:
                return

    # -- coordinator --
    def integrate(self) -> list[dict]:
        results = []
        for _ in range(12):
            self.tick()
            result = self.queue.worker(self.root)
            results.append({k: v for k, v in result.items() if k in {"state", "number", "reason"}})
            self.settle()
            if result["state"] in {"empty", "merged"} and all(self.github.prs[str(n)]["merged"] for n in self.numbers.values()):
                break
        return results

    # -- run --
    def run(self) -> dict:
        started = time.monotonic()
        summary: dict | None = None
        failure: BaseException | None = None
        try:
            self.setup()
            self.modules()
            initial_main = self.remote_head("main")
            self.admit_all()
            admitted_states = {c["number"]: c["state"] for c in self.candidates()}
            self.settle()
            before_merge = {c["number"]: c["state"] for c in self.candidates()}
            merges = self.integrate()
            final_main = self.remote_head("main")
            summary = self.summarize(initial_main, final_main, admitted_states, before_merge, merges,
                                     time.monotonic() - started)
            self.verify(summary)
        except BaseException as exc:  # recorded below, then re-raised after cleanup
            failure = exc
        return self.finish(summary, failure, time.monotonic() - started)

    def finish(self, summary: dict | None, failure: BaseException | None, seconds: float) -> dict:
        """Always leave evidence and clean the sandboxes, with containment verified, also on failure."""
        summary = summary if summary is not None else {"version": 1, "seconds": round(seconds, 2)}
        try:
            if hasattr(self, "sandboxes") and getattr(self, "seed_digest", None) is not None:
                self.cleanup(summary)
        except (ScenarioError, subprocess.SubprocessError, OSError) as exc:
            summary["containment"] = {"error": str(exc)}
            failure = failure or exc
        if failure is not None:
            summary["failure"] = str(failure)
        if hasattr(self, "github"):
            put(self.output / "trace.json", json.dumps({"comments": self.github.comments, "calls": self.github.calls},
                                                       indent=1, sort_keys=True) + "\n")
        if self.output.is_dir():
            put(self.output / "summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
        if failure is not None:
            raise failure
        return summary

    # -- evidence --
    def summarize(self, initial_main, final_main, admitted, before_merge, merges, seconds) -> dict:
        prefix = self.lifecycle.PREFIX
        w = self.workers_module
        aliases: dict[str, str] = {}
        names = {str(n): letter for letter, n in self.numbers.items()}

        def alias(head: Any) -> str | None:
            if not isinstance(head, str):
                return None
            return aliases.setdefault(head, f"h{len(aliases) + 1}")

        events = []
        rows = sorted(((c["id"], n, c) for n, comments in self.github.comments.items() for c in comments), key=lambda r: r[0])
        for _, number, comment in rows:
            who, body = names[number], comment["body"]
            if body.startswith(prefix):
                record = json.loads(body[len(prefix):])
                job = record.get("next_job") if isinstance(record.get("next_job"), dict) else {}
                events.append([who, "record", record.get("state"), alias(record.get("head")),
                               f"{job.get('kind')}:{job.get('attempt')}" if job else None,
                               (record.get("red_gate") or {}).get("name")])
            elif body.startswith(self.queue.PREFIX):
                record = json.loads(body[len(self.queue.PREFIX):])
                events.append([who, "marker", record.get("kind"), alias(record.get("head")), None, None])
            elif body.startswith(w.CLAIM_PREFIX):
                record = json.loads(body[len(w.CLAIM_PREFIX):])
                events.append([who, "claim", ":".join(record["job"].split(":")[1:2] + record["job"].split(":")[3:]),
                               alias(record.get("head")), record["worker"], None])
            elif body.startswith(w.RESULT_PREFIX):
                record = json.loads(body[len(w.RESULT_PREFIX):])
                parts = record["job"].split(":")
                events.append([who, "result", f"{parts[1]}:{parts[3]}", alias(record.get("head")),
                               str(record.get("outcome")).split(":")[0], alias(record.get("pushed_head"))])
        mutations = [[names.get(str(c.get("number")), "-"), c["mutation"]] for c in self.github.calls
                     if c.get("mutation") in {"merge", "update-branch"}]
        return {
            "version": 1, "repo": REPO, "requirement": REQUIREMENT, "seconds": round(seconds, 2),
            "actions": self.actions, "initial_main": initial_main, "final_main": final_main,
            "admitted_states": {names[str(n)]: s for n, s in admitted.items()},
            "states_before_first_merge": {names[str(n)]: s for n, s in before_merge.items()},
            "coordinator_runs": merges,
            "merged": {names[n]: pr["merged"] for n, pr in self.github.prs.items()},
            "transitions": events, "merge_operations": mutations,
            "operator_actions": self.github.operator_actions, "developer_actions": self.developer_actions,
            "unsupported_gh_calls": [c["argv"] for c in self.github.calls if c.get("unsupported")],
            "gh_calls": len(self.github.calls),
            "reviewer_contexts": sum(1 for call in self.llm_calls if call == ["reviewer-context"]),
        }

    def verify(self, summary: dict) -> None:
        problems = []
        problems += structure_problems(summary)
        for letter, change, _, _ in CANDIDATES:
            lower = letter.lower()
            if not git(self.remote, "show", f"main:src_{lower}.py", check=False):
                problems.append(f"candidate {letter} content is absent from final main")
            if change and not git(self.remote, "show", f"main:openspec/specs/cap-{lower}/spec.md", check=False):
                problems.append(f"candidate {letter} spec is not materialized on final main")
        if "BUG" in git(self.remote, "show", "main:src_b.py"):
            problems.append("the reviewed defect reached main")
        shared = git(self.remote, "show", "main:shared.py")
        if "VALUE = 5" not in shared or "OTHER = 'b'" not in shared or "<<<<" in shared:
            problems.append("shared.py lacks the resolved A+C and B contributions")
        from openspec_lifecycle import completed_active_changes_at

        git(self.root, "fetch", "-q", "origin")
        if completed_active_changes_at(self.root, "origin/main"):
            problems.append("a completed OpenSpec change is still active on main")
        problems += post_merge_problems(summary["transitions"])
        if problems:
            raise ScenarioError("; ".join(problems))

    def cleanup(self, summary: dict) -> None:
        script = SCRIPTS / "disposable_repository_sandbox.py"
        os.chdir(self.output)
        for name in self.sandboxes:
            done = subprocess.run([sys.executable, str(script), "cleanup", str(self.sandbox), name], text=True,
                                  capture_output=True, stdin=subprocess.DEVNULL, check=False, timeout=60)
            if done.returncode:
                raise ScenarioError(f"sandbox containment check failed: {done.stderr.strip()}")
        if tree_digest(self.seed) != self.seed_digest:
            raise ScenarioError("the sandbox source repository changed during the scenario")
        summary["containment"] = {"sandboxes_verified_and_removed": list(self.sandboxes), "source_unchanged": True}


def run(output: Path, *, max_actions: int = MAX_ACTIONS) -> dict:
    def expired(signum, frame):
        raise ScenarioError(f"scenario deadline of {DEADLINE_SECONDS}s exceeded")

    signal.signal(signal.SIGALRM, expired)
    signal.alarm(DEADLINE_SECONDS)
    try:
        return Scenario(output, max_actions=max_actions).run()
    finally:
        signal.alarm(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    runner = commands.add_parser("run")
    runner.add_argument("--output", required=True, help="empty or absent directory for the run's evidence")
    runner.add_argument("--max-actions", type=int, default=MAX_ACTIONS)
    args = parser.parse_args(argv)
    try:
        summary = run(Path(args.output), max_actions=args.max_actions)
    except (ScenarioError, subprocess.SubprocessError, OSError, KeyError, RuntimeError) as exc:
        print(f"parallel lifecycle acceptance failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: summary[key] for key in ("merged", "seconds", "actions", "gh_calls")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
