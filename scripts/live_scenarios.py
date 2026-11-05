#!/usr/bin/env python3
"""Run lifecycle scenarios on the real GitHub sandbox repository.

The runner acts as developer and coordinator through documented platform entrypoints only.
It never edits labels, lifecycle comments or queue records. See docs/engineering/live-scenarios.md.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_scenario_gate  # noqa: E402

SOURCE_ROOT = Path(__file__).resolve().parents[1]
SANDBOX_DIR = SOURCE_ROOT / "dev-platform" / "live-sandbox"
HEAD_MARKER = Path("dev-platform") / "live-sandbox-head.txt"
WORKDIR_MARKER = ".live-sandbox-workdir"
LOCK_VARIABLE = "LIVE_SCENARIO_LOCK"
LOCK_LEASE_SECONDS = 3 * 3600
POLL_SECONDS = 15
HANDOFF = "Developer handoff complete"
CLAUDE_BIN_ENV = "DEV_PLATFORM_CLAUDE_BIN"
VERIFICATION = """# Verification: {change}

OpenSpec-Verify: PASS
Verification-Method: scripted live scenario check of the fixture note against the delta spec.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Semantic assessment

- The note file exists as the spec requires. Round {round}.
"""
QUEUED = "Publication queued; rerun finish after GitHub reports the exact PR MERGED."
TOKEN_ANCHOR = "permission-pull-requests: write"
OWNER_SECRET = "DEV_PLATFORM_APP_PRIVATE_KEY"
OWNER_VARIABLE = "DEV_PLATFORM_APP_CLIENT_ID"
PROJECT_LABEL = "project:dev-platform-sandbox"
PROJECT_STATUSES = ("Backlog", "Ready", "In progress", "In review", "Blocked", "Done")
BACKLOG_LABELS = (PROJECT_LABEL, "priority:P0", "priority:P1", "priority:P2", "priority:P3", "type:requirement", "type:internal-change")


class SandboxError(RuntimeError):
    """A precondition failed before or outside a scenario step."""


class StepFailure(RuntimeError):
    """A scenario step did not reach its expected state."""

    def __init__(self, scenario: str, step: str, observed: str):
        super().__init__(f"scenario {scenario}: step {step} failed: {observed}")
        self.scenario, self.step, self.observed = scenario, step, observed


@dataclass(frozen=True)
class Config:
    repository: str
    coordinator_app: str
    coordinator_app_id: int
    required_check: str
    hosted_kinds: str
    kept_workflows: tuple[str, ...]
    dropped_paths: tuple[str, ...]
    token_read_permissions: tuple[str, ...]
    project_title: str


def load_config(path: Path = SANDBOX_DIR / "sandbox.toml") -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    try:
        return Config(data["repository"], data["coordinator_app"], data["coordinator_app_id"], data["required_check"],
                      data["hosted_kinds"], tuple(data["kept_workflows"]), tuple(data["dropped_paths"]),
                      tuple(data["token_read_permissions"]), data["project_title"])
    except KeyError as missing:
        raise SandboxError(f"{path} lacks required key {missing}") from missing


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None, *, input_text: str | None = None) -> str:
    """Run one command; a failure names the command and its output, which never holds a token."""
    done = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False, input=input_text,
                          stdin=None if input_text is not None else subprocess.DEVNULL)
    if done.returncode:
        output = "\n".join(part for part in (done.stdout.strip(), done.stderr.strip()) if part)
        error = SandboxError(f"{' '.join(command[:4])} exited {done.returncode}: {output[-2000:]}")
        error.output = output
        raise error
    return done.stdout


def gh_json(args: list[str], cwd: Path) -> Any:
    return json.loads(run(["gh", *args], cwd) or "null")


def assert_target(config: Config, repository: str, *, source_origin: str, private: bool) -> None:
    """Refuse before any write unless the target is exactly the configured private sandbox."""
    if repository != config.repository:
        raise SandboxError(f"target {repository} is not the configured sandbox {config.repository}")
    if repository in source_origin:
        raise SandboxError(f"target {repository} is this platform checkout's own origin")
    if not private:
        raise SandboxError(f"target {repository} is not private")


def check_target(config: Config) -> None:
    view = gh_json(["repo", "view", config.repository, "--json", "nameWithOwner,isPrivate"], SOURCE_ROOT)
    origin = run(["git", "remote", "get-url", "origin"], SOURCE_ROOT).strip()
    assert_target(config, view["nameWithOwner"], source_origin=origin, private=view["isPrivate"])


def check_owner_setup(config: Config) -> None:
    """The App secret and id are owner steps; a missing one stops with that step named."""
    secrets = {item["name"] for item in gh_json(["secret", "list", "--repo", config.repository, "--json", "name"], SOURCE_ROOT)}
    variables = {item["name"] for item in gh_json(["variable", "list", "--repo", config.repository, "--json", "name"], SOURCE_ROOT)}
    if OWNER_SECRET not in secrets:
        raise SandboxError(f"secret {OWNER_SECRET} is missing on {config.repository}: owner step in docs/engineering/live-scenarios.md")
    if OWNER_VARIABLE not in variables:
        raise SandboxError(f"variable {OWNER_VARIABLE} is missing on {config.repository}: owner step in docs/engineering/live-scenarios.md")


def compose_snapshot(head: str, destination: Path, config: Config, source: Path = SOURCE_ROOT) -> None:
    """Write the tree of ``head`` plus the fixture overlay into an empty ``destination``."""
    archive = destination.parent / f"{destination.name}.tar"
    run(["git", "archive", "--format=tar", "-o", str(archive), head], source)
    with tarfile.open(archive) as tar:
        tar.extractall(destination, filter="data")
    archive.unlink()
    overlay = destination / "dev-platform" / "live-sandbox" / "overlay"
    if not overlay.is_dir():
        raise SandboxError(f"head {head} lacks the fixture overlay")
    staged_overlay = destination.parent / f"{destination.name}.overlay"
    shutil.move(overlay, staged_overlay)
    for relative in config.dropped_paths:
        target = destination / relative
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    workflows = destination / ".github" / "workflows"
    for path in workflows.iterdir():
        if path.name not in config.kept_workflows:
            path.unlink()
    missing = [name for name in config.kept_workflows if not (workflows / name).is_file()]
    if missing:
        raise SandboxError(f"head {head} lacks workflows {missing}")
    for name in config.kept_workflows:
        grant_token_reads(workflows / name, config.token_read_permissions)
    shutil.copytree(staged_overlay, destination, dirs_exist_ok=True)
    shutil.rmtree(staged_overlay)
    (destination / HEAD_MARKER).write_text(head + "\n", encoding="utf-8")


def grant_token_reads(workflow: Path, permissions: tuple[str, ...]) -> None:
    """Add the private-repository reads to every App token a kept workflow mints.

    This is the one deliberate difference from the platform's workflows, and a workflow whose
    token step changed shape stops the snapshot rather than running without the grant.
    """
    lines, found = [], 0
    for line in workflow.read_text(encoding="utf-8").splitlines(keepends=True):
        lines.append(line)
        if line.strip() == TOKEN_ANCHOR:
            found += 1
            indent = line[:len(line) - len(line.lstrip())]
            lines.extend(f"{indent}permission-{name}: read\n" for name in permissions)
    if not found:
        raise SandboxError(f"{workflow.name} has no `{TOKEN_ANCHOR}` line to extend with {list(permissions)}")
    workflow.write_text("".join(lines), encoding="utf-8")


def share_with_group(root: Path) -> None:
    """Give the checkout the group modes the shared-workspace preflight requires of a platform checkout."""
    group = os.getgid()  # setgid is cleared on a group the account is not in, as with a temporary directory
    for directory, _, files in os.walk(root):
        os.chown(directory, -1, group)
        os.chmod(directory, os.stat(directory).st_mode | 0o2770)
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                os.chown(path, -1, group)
                os.chmod(path, path.stat().st_mode | 0o040 if ".git/objects/" in str(path) else path.stat().st_mode | 0o060)


class Lock:
    """One live run per sandbox: an Actions variable holding the run id and its lease expiry.

    Creating an existing variable fails, so two starts cannot both win; an expired lease is a dead run.
    """

    def __init__(self, config: Config, *, now: Callable[[], float] = time.time):
        self.repository, self.now, self.run_id = config.repository, now, uuid.uuid4().hex[:12]

    def _path(self, name: str = "") -> str:
        return f"repos/{self.repository}/actions/variables{name}"

    def _create(self) -> bool:
        value = f"{self.run_id} {int(self.now()) + LOCK_LEASE_SECONDS}"
        done = subprocess.run(["gh", "api", "-X", "POST", self._path(), "-f", f"name={LOCK_VARIABLE}", "-f", f"value={value}"],
                              cwd=SOURCE_ROOT, text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
        if done.returncode == 0:
            return True
        if "409" in done.stderr or "already exists" in done.stderr:
            return False
        raise SandboxError(f"creating {LOCK_VARIABLE} failed: {done.stderr.strip()[-500:]}")

    def acquire(self) -> None:
        if self._create():
            return
        holder = gh_json(["api", self._path(f"/{LOCK_VARIABLE}")], SOURCE_ROOT)["value"].split()
        if int(holder[1]) > self.now():
            raise SandboxError(f"run {holder[0]} holds the sandbox until epoch {holder[1]}")
        run(["gh", "api", "-X", "DELETE", self._path(f"/{LOCK_VARIABLE}")], SOURCE_ROOT)
        if not self._create():
            raise SandboxError("another run took the expired sandbox lock first")

    def release(self) -> None:
        run(["gh", "api", "-X", "DELETE", self._path(f"/{LOCK_VARIABLE}")], SOURCE_ROOT)


class Sandbox:
    """The real sandbox repository and a runner-owned local checkout of it."""

    def __init__(self, config: Config, workdir: Path, head: str):
        self.config, self.workdir, self.head = config, workdir.resolve(), head
        self.checkout = self.workdir / "integration"

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.config.repository}.git"

    def env(self) -> dict[str, str]:
        # Fixture checks take seconds and must not queue behind real validation on the machine pool.
        env = {key: value for key, value in os.environ.items()
               if key not in {"CLAUDE_CODE_OAUTH_TOKEN", "DEV_PLATFORM_MACHINE_POOL", "DEV_PLATFORM_MACHINE_POOL_LEASE"}}
        env["GH_TOKEN"] = run(["gh", "auth", "token"], SOURCE_ROOT).strip()
        env["DEV_PLATFORM_OPERATOR_CONFIG"] = str(self.workdir / "operator.toml")
        env[CLAUDE_BIN_ENV] = str(self.workdir / "executors" / "claude")
        return env

    def prepare_workdir(self) -> None:
        marker = self.workdir / WORKDIR_MARKER
        if self.workdir.exists() and any(self.workdir.iterdir()) and not marker.is_file():
            raise SandboxError(f"{self.workdir} is not empty and is not a runner workdir")
        if self.workdir.exists():
            shutil.rmtree(self.workdir)
        self.workdir.mkdir(parents=True)
        marker.write_text(self.config.repository + "\n", encoding="utf-8")
        (self.workdir / "managed-projects.json").write_text(json.dumps({
            "version": 1, "projects": [{"repository": self.config.repository, "state": "managed", "default_branch": "main",
                                        "note": "Live scenario sandbox; private to this runner."}]}), encoding="utf-8")
        (self.workdir / "operator.toml").write_text(
            f'[rollout]\nregistry_path = "{self.workdir / "managed-projects.json"}"\n\n'
            f'[publication]\ncoordinator_app = "{self.config.coordinator_app}"\n', encoding="utf-8")

    def close_open_work(self) -> None:
        repo = self.config.repository
        for pr in gh_json(["pr", "list", "--repo", repo, "--state", "open", "--limit", "200", "--json", "number"], SOURCE_ROOT):
            run(["gh", "pr", "close", str(pr["number"]), "--repo", repo], SOURCE_ROOT)
        for issue in gh_json(["issue", "list", "--repo", repo, "--state", "open", "--limit", "200", "--json", "number"], SOURCE_ROOT):
            run(["gh", "issue", "close", str(issue["number"]), "--repo", repo], SOURCE_ROOT)
        for ref in gh_json(["api", "--paginate", f"repos/{repo}/branches?per_page=100"], SOURCE_ROOT) or []:
            if ref["name"] != "main":
                run(["gh", "api", "-X", "DELETE", f"repos/{repo}/git/refs/heads/{ref['name']}"], SOURCE_ROOT)

    def install_baseline(self) -> None:
        """Commit the baseline tree forward on main, never rewriting history."""
        env = self.env()
        checkout = self.checkout
        checkout.mkdir()
        run(["git", "init", "-q", "--shared=group", "-b", "main"], checkout)
        run(["git", "remote", "add", "origin", self.clone_url], checkout)
        run(["git", "config", "user.name", "Live scenario runner"], checkout)
        run(["git", "config", "user.email", "live-scenarios@localhost"], checkout)
        run(["git", "config", "credential.helper", "!gh auth git-credential"], checkout)
        remote = run(["git", "ls-remote", "origin", "refs/heads/main"], checkout, env).split()
        if remote:
            run(["git", "fetch", "-q", "origin", "main"], checkout, env)
            run(["git", "reset", "-q", "--hard", "FETCH_HEAD"], checkout)
        with tempfile.TemporaryDirectory(dir=self.workdir) as temporary:
            tree = Path(temporary) / "tree"
            tree.mkdir()
            compose_snapshot(self.head, tree, self.config)
            for path in checkout.iterdir():
                if path.name != ".git":
                    shutil.rmtree(path) if path.is_dir() else path.unlink()
            shutil.copytree(tree, checkout, dirs_exist_ok=True)
        run(["git", "add", "-A"], checkout)
        if run(["git", "status", "--porcelain"], checkout).strip():
            run(["git", "commit", "-q", "-m", f"Sandbox baseline at {self.head}"], checkout)
            run(["git", "push", "-q", "origin", "HEAD:refs/heads/main"], checkout, env)
        self.install_local_contract()
        share_with_group(self.workdir)

    def install_local_contract(self) -> None:
        """Install the runner-owned contract: the committed one plus operator sections naming only this sandbox."""
        contract = (self.checkout / "dev-platform" / "source-contract.toml").read_text(encoding="utf-8")
        owner, _ = self.config.repository.split("/")
        (self.checkout / ".dev-platform.toml").write_text(
            contract + '\n[operator]\nenabled = true\nconfig_env = "DEV_PLATFORM_OPERATOR_CONFIG"\n'
            f'\n[development_backlog]\nrepository = "{self.config.repository}"\n'
            f'project_label = "{PROJECT_LABEL}"\ndefault_priority = "P2"\nproject_owner = "{owner}"\n'
            f'project_number = {self.ensure_project()}\n'
            f'\n[agent_sessions]\ndirectory = "{self.workdir / "agent-sessions"}"\nstale_after_seconds = 21600\nended_keep_seconds = 86400\n',
            encoding="utf-8")
        with (self.checkout / ".git" / "info" / "exclude").open("a", encoding="utf-8") as handle:
            handle.write(".dev-platform.toml\n.claude/\n")

    def author_bundle(self, slug: str) -> Path:
        """A managed bundle for one scenario: the change and capability carry its slug, so runs never collide."""
        target = self.workdir / "bundles" / slug
        shutil.copytree(SANDBOX_DIR / "managed-bundle", target)
        (target / "specs" / "fixture-note").rename(target / "specs" / slug)
        for path in target.rglob("*"):
            if path.is_file():
                path.write_text(path.read_text(encoding="utf-8").replace("fixture-note", slug), encoding="utf-8")
        return target

    def script_review(self, findings: list[dict[str, str]]) -> None:
        """Set what the scripted reviewer answers from now on."""
        (self.workdir / "executors" / "findings.json").write_text(json.dumps(findings), encoding="utf-8")

    def scripted_writer(self, edits: dict[str, str]) -> str:
        """The --llm-command of a repair that writes exactly ``edits``."""
        control = self.workdir / "executors" / f"edits-{uuid.uuid4().hex[:8]}.json"
        control.write_text(json.dumps(edits), encoding="utf-8")
        return shlex.join(["python3", str(SANDBOX_DIR / "executors" / "scripted_writer.py"), str(control)])

    def install_executors(self) -> None:
        """The reviewer CLI the workers launch through the documented binary override."""
        directory = self.workdir / "executors"
        directory.mkdir()
        self.script_review([])
        claude = directory / "claude"
        claude.write_text("#!/bin/sh\nexec " + shlex.join(["python3", str(SANDBOX_DIR / "executors" / "scripted_claude.py"),
                                                           str(directory / "findings.json")]) + ' "$@"\n', encoding="utf-8")
        claude.chmod(0o755)

    def ensure_project(self) -> int:
        """The sandbox's own Backlog Project with the platform statuses; created once, reconciled on every reset."""
        owner, title = self.config.repository.split("/")[0], self.config.project_title
        listed = gh_json(["project", "list", "--owner", owner, "--limit", "100", "--format", "json"], SOURCE_ROOT)["projects"]
        found = [item["number"] for item in listed if item["title"] == title]
        number = found[0] if found else gh_json(["project", "create", "--owner", owner, "--title", title, "--format", "json"], SOURCE_ROOT)["number"]
        fields = gh_json(["project", "field-list", str(number), "--owner", owner, "--format", "json"], SOURCE_ROOT)["fields"]
        status = next(field for field in fields if field["name"] == "Status")
        if {option["name"] for option in status["options"]} != set(PROJECT_STATUSES):
            options = ", ".join(f'{{name: "{name}", color: GRAY, description: ""}}' for name in PROJECT_STATUSES)
            query = f'mutation {{ updateProjectV2Field(input: {{fieldId: "{status["id"]}", singleSelectOptions: [{options}]}}) {{ clientMutationId }} }}'
            run(["gh", "api", "graphql", "-f", f"query={query}"], SOURCE_ROOT)
        return number

    def apply_settings(self) -> None:
        """Idempotent repository settings matching production main, plus the admin path of the baseline write."""
        repo, config = self.config.repository, self.config
        current = gh_json(["api", f"repos/{repo}"], SOURCE_ROOT)
        if not current["allow_squash_merge"] or current["delete_branch_on_merge"]:
            run(["gh", "api", "-X", "PATCH", f"repos/{repo}", "-F", "allow_squash_merge=true", "-F", "delete_branch_on_merge=false",
                 "--jq", ".name"], SOURCE_ROOT)
        run(["gh", "variable", "set", "DEV_PLATFORM_HOSTED_KINDS", "--repo", repo, "--body", config.hosted_kinds], SOURCE_ROOT)
        for label in BACKLOG_LABELS:
            run(["gh", "label", "create", label, "--repo", repo, "--force"], SOURCE_ROOT)
        protection = {"required_status_checks": {"strict": True, "contexts": [config.required_check]},
                      "enforce_admins": False, "required_pull_request_reviews": None, "restrictions": None}
        run(["gh", "api", "-X", "PUT", f"repos/{repo}/branches/main/protection", "--input", "-"], SOURCE_ROOT,
            input_text=json.dumps(protection))
        name = "main: sandbox coordinator only"
        rules = gh_json(["api", f"repos/{repo}/rulesets"], SOURCE_ROOT)
        if not any(rule["name"] == name for rule in rules):
            ruleset = {"name": name, "target": "branch", "enforcement": "active",
                       "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                       "rules": [{"type": "update"}, {"type": "deletion"}, {"type": "non_fast_forward"}],
                       "bypass_actors": [{"actor_id": config.coordinator_app_id, "actor_type": "Integration", "bypass_mode": "pull_request"},
                                         {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]}
            run(["gh", "api", "-X", "POST", f"repos/{repo}/rulesets", "--input", "-"], SOURCE_ROOT, input_text=json.dumps(ruleset))

    def reset(self) -> None:
        self.prepare_workdir()
        self.install_executors()
        self.close_open_work()
        self.install_baseline()
        self.apply_settings()
        self.check_app_token()


    def check_app_token(self) -> None:
        """Run the queue once: the token step fails when the App lacks a permission the snapshot requests."""
        repo = self.config.repository
        before = {item["databaseId"] for item in self.queue_runs()}
        run(["gh", "workflow", "run", "publication-queue.yml", "--repo", repo], SOURCE_ROOT)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            fresh = [item for item in self.queue_runs() if item["databaseId"] not in before]
            if fresh and fresh[0]["status"] == "completed":
                if fresh[0]["conclusion"] == "success":
                    return
                view = gh_json(["run", "view", str(fresh[0]["databaseId"]), "--repo", repo, "--json", "jobs"], SOURCE_ROOT)
                failed = [step["name"] for job in view["jobs"] for step in job["steps"] if step["conclusion"] == "failure"]
                raise SandboxError(f"queue run {fresh[0]['databaseId']} failed at {failed}: the App "
                                   f"{self.config.coordinator_app} must grant {list(self.config.token_read_permissions)} read")
            time.sleep(POLL_SECONDS)
        raise SandboxError("the queue token check run did not complete within 300s")

    def queue_runs(self) -> list[dict[str, Any]]:
        return gh_json(["run", "list", "--repo", self.config.repository, "--workflow", "publication-queue.yml",
                        "--event", "workflow_dispatch", "--limit", "5", "--json", "databaseId,status,conclusion"], SOURCE_ROOT)


class Scenario:
    """One scenario run: named steps, each failing with the observed state."""

    def __init__(self, name: str, sandbox: Sandbox):
        self.name, self.sandbox, self.current = name, sandbox, ""

    def step(self, name: str) -> None:
        self.current = name
        print(f"[{self.name}] {name}", flush=True)

    def fail(self, observed: str) -> StepFailure:
        return StepFailure(self.name, self.current, observed)

    def platform(self, script: str, *args: str, cwd: Path | None = None) -> str:
        try:
            return run(["python3", f"scripts/{script}", *args], cwd or self.sandbox.checkout, self.sandbox.env())
        except SandboxError as error:
            raise self.fail(str(error)) from error

    def finish_until_queued(self, worktree: Path, title: str) -> None:
        """First finish publishes and hands the PR to the queue, which it reports by exiting 2 with QUEUED."""
        try:
            run(["python3", "scripts/dogfood_task.py", "finish", "--title", title, "--body", "Live scenario."],
                worktree, self.sandbox.env())
        except SandboxError as error:
            if QUEUED not in getattr(error, "output", ""):
                raise self.fail(str(error)) from error
        else:
            raise self.fail("finish returned without queueing the PR")

    def start_managed(self, slug: str) -> Path:
        """Author, list and start one managed task; returns its task worktree."""
        bundle = self.sandbox.author_bundle(slug)
        created = self.platform("managed_task.py", "create", "--bundle", str(bundle), "--confirm-distinct")
        found = re.search(r"Managed task created: (\S+#\d+)", created)
        if found is None:
            raise self.fail(f"no managed Issue in: {created[-500:]}")
        self.platform("managed_project_status.py", "ensure", "--issue", found.group(1))
        self.platform("start_managed_task.py", found.group(1))
        worktree = self.sandbox.checkout / ".claude" / "worktrees" / slug
        if not worktree.is_dir():
            raise self.fail("no task worktree after managed start")
        self.platform("dogfood_task.py", "route-claude", "--tier", "R2", "--rationale", "Live scenario",
                      "--evidence", "Fixture change", cwd=worktree)
        return worktree

    def hand_off(self, worktree: Path, slug: str, base: str, title: str, round_: int = 1) -> None:
        """The developer path of a managed change after its file edits: receipt, evidence, friction, finish."""
        change = worktree / "openspec" / "changes" / slug
        tasks = change / "tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        (change / "verification.md").write_text(VERIFICATION.format(change=slug, round=round_), encoding="utf-8")
        run(["git", "add", "-A"], worktree)
        run(["git", "commit", "-q", "-m", f"Implement {slug}, round {round_}"], worktree)
        self.platform("select_checks.py", "--base", base, "--execute", "--evidence",
                      f"openspec/changes/{slug}/automated-checks.json", cwd=worktree)
        run(["git", "add", "-A"], worktree)
        run(["git", "commit", "-q", "-m", f"Record evidence of {slug}, round {round_}"], worktree)
        if round_ == 1:
            self.platform("model_routing.py", "record-retained-execution", "--reason", "Live scenario", cwd=worktree)
        self.platform("agent_friction.py", "checkpoint", "--result", "none", "--review-note", "Live scenario", cwd=worktree)
        done = self.platform("dogfood_task.py", "finish", "--title", title, "--body", "Live scenario.", cwd=worktree)
        if HANDOFF not in done:
            raise self.fail(f"finish did not hand off: {done[-500:]}")

    def worker(self, kind: str, number: int, *extra: str) -> None:
        """One coordinator worker run through the documented entrypoint, with the scripted executors."""
        self.platform("lifecycle_workers.py", "work-next", "--kinds", kind, "--repo", self.sandbox.config.repository,
                      "--pr", str(number), "--provider", "claude", "--run", *extra)

    def repair_worker(self, kind: str, number: int, edits: dict[str, str], allow: list[str]) -> None:
        command = self.sandbox.scripted_writer(edits)
        self.worker(kind, number, "--llm-command", command, *[item for path in allow for item in ("--allow", path)])

    def queue_state(self, number: int) -> dict[str, Any]:
        status = run(["python3", "template/scripts/publication_queue.py", "status", "--pr", str(number), "--json"],
                     self.sandbox.checkout, self.sandbox.env())
        return json.loads(status)

    def wait_queue(self, number: int, states: set[str], limit: int) -> dict[str, Any]:
        """Wait for one of ``states`` or the PR's merge; any other terminal escalation stops the scenario."""
        def done(state: dict[str, Any]) -> bool:
            if state["state"] == "blocked-escalation" and "blocked-escalation" not in states:
                raise self.fail(f"escalated: {str(state.get('red_gate'))[:800]}")
            return state["state"] in states
        return self.wait(lambda: self.queue_state(number), done, limit)

    def expect_merged(self, branch: str, limit: int = 1200) -> dict[str, Any]:
        def done(pr: dict[str, Any]) -> bool:
            if "lifecycle:blocked-escalation" in {label["name"] for label in pr.get("labels", [])}:
                raise self.fail(f"escalated: {str(self.queue_state(pr['number']).get('red_gate'))[:800]}")
            return pr.get("state") == "MERGED"
        final = self.wait(lambda: self.pr_state(branch), done, limit)
        merger = (final.get("mergedBy") or {}).get("login", "")
        if self.sandbox.config.coordinator_app not in merger:
            raise self.fail(f"merged by {merger!r}, not the coordinator App")
        return final

    def expect_on_main(self, path: str, text: str) -> None:
        repo = self.sandbox.config.repository
        content = gh_json(["api", f"repos/{repo}/contents/{path}?ref=main"], SOURCE_ROOT)
        if text not in base64.b64decode(content["content"]).decode("utf-8"):
            raise self.fail(f"{path} on main does not hold {text!r}")

    def wait(self, read: Callable[[], Any], done: Callable[[Any], bool], limit: int) -> Any:
        deadline = time.monotonic() + limit
        while True:
            observed = read()
            if done(observed):
                return observed
            if time.monotonic() >= deadline:
                raise self.fail(f"not reached within {limit}s, last observed: {str(observed)[:800]}")
            time.sleep(POLL_SECONDS)

    def pr_state(self, branch: str) -> dict[str, Any]:
        prs = gh_json(["pr", "list", "--repo", self.sandbox.config.repository, "--head", branch, "--state", "all",
                       "--json", "number,state,labels,headRefOid,mergedBy"], SOURCE_ROOT)
        return prs[0] if prs else {}


def quick_change(scenario: Scenario, slug: str, edits: dict[str, str]) -> tuple[Path, str]:
    """Start a quick task and commit ``edits`` through the developer entrypoints, up to the friction checkpoint."""
    output = scenario.platform("dogfood_task.py", "start", slug, "--task", f"Live scenario {slug}")
    worktree = scenario.sandbox.checkout / ".claude" / "worktrees" / slug
    if not worktree.is_dir():
        raise scenario.fail(f"no task worktree after start: {output[-500:]}")
    for relative, content in edits.items():
        (worktree / relative).write_text(content, encoding="utf-8")
    run(["git", "add", "-A"], worktree)
    run(["git", "commit", "-q", "-m", f"Change {slug}"], worktree)
    scenario.platform("agent_friction.py", "checkpoint", "--result", "none", "--review-note", "Live scenario", cwd=worktree)
    return worktree, run(["git", "branch", "--show-current"], worktree).strip()


def scenario_quick_task(scenario: Scenario) -> None:
    slug = f"quick-{uuid.uuid4().hex[:8]}"
    scenario.step("start, change and friction checkpoint")
    worktree, branch = quick_change(scenario, slug, {f"fixture/{slug}.txt": slug + "\n"})
    scenario.step("finish")
    scenario.finish_until_queued(worktree, f"Quick {slug}")
    scenario.step("queue merges")
    scenario.expect_merged(branch, 900)
    scenario.step("finish after merge")
    scenario.platform("dogfood_task.py", "finish", cwd=worktree)
    scenario.step("final state")
    scenario.expect_on_main(f"fixture/{slug}.txt", slug)


def scenario_red_ci(scenario: Scenario) -> None:
    """Required CI fails on the admitted head; the queue's own exit brings the candidate to MERGED."""
    slug = f"red-{uuid.uuid4().hex[:8]}"
    scenario.step("start, change and friction checkpoint")
    worktree, branch = quick_change(scenario, slug, {f"fixture/{slug}.txt": slug + "\n", "fixture/ci-verdict.txt": "red\n"})
    scenario.step("finish")
    scenario.finish_until_queued(worktree, f"Red {slug}")
    number = scenario.pr_state(branch)["number"]
    scenario.step("queue offers repair of the red check")
    scenario.wait_queue(number, {"integration-repair-pending"}, 600)
    scenario.step("integration repair")
    scenario.repair_worker("integration-repair", number, {"fixture/ci-verdict.txt": "green\n"}, ["fixture"])
    scenario.step("queue merges")
    scenario.expect_merged(branch, 900)
    scenario.step("final state")
    scenario.expect_on_main("fixture/ci-verdict.txt", "green")
    scenario.expect_on_main(f"fixture/{slug}.txt", slug)


def scenario_conflict(scenario: Scenario) -> None:
    """Main moves with a conflicting line after admission; the queue offers integration repair."""
    sandbox, slug = scenario.sandbox, f"conflict-{uuid.uuid4().hex[:8]}"
    repo, path = sandbox.config.repository, "fixture/shared.txt"
    scenario.step("start, change and friction checkpoint")
    worktree, branch = quick_change(scenario, slug, {path: f"{slug} candidate\n"})
    scenario.step("finish")
    scenario.finish_until_queued(worktree, f"Conflict {slug}")
    number = scenario.pr_state(branch)["number"]
    scenario.step("main moves with a conflicting change")
    current = gh_json(["api", f"repos/{repo}/contents/{path}?ref=main"], SOURCE_ROOT)
    moved = base64.b64encode(f"{slug} main\n".encode()).decode()
    run(["gh", "api", "-X", "PUT", f"repos/{repo}/contents/{path}", "-f", f"message=Move main for {slug}", "-f", f"content={moved}",
         "-f", f"sha={current['sha']}", "-f", "branch=main", "--jq", ".commit.sha"], SOURCE_ROOT)
    scenario.step("queue offers integration repair")
    scenario.wait_queue(number, {"integration-repair-pending"}, 600)
    scenario.step("integration repair")
    resolved = f"{slug} main\n{slug} candidate\n"
    scenario.repair_worker("integration-repair", number, {path: resolved}, ["fixture"])
    scenario.step("queue merges the repaired head")
    scenario.expect_merged(branch, 900)
    scenario.step("final state")
    scenario.expect_on_main(path, resolved)


def scenario_managed_task(scenario: Scenario) -> None:
    sandbox = scenario.sandbox
    slug = f"managed-{uuid.uuid4().hex[:8]}"
    scenario.step("start")
    worktree = scenario.start_managed(slug)
    base = run(["git", "merge-base", "HEAD", "origin/main"], worktree).strip()
    scenario.step("change and handoff")
    (worktree / "fixture" / f"{slug}.txt").write_text(slug + "\n", encoding="utf-8")
    scenario.hand_off(worktree, slug, base, f"Managed {slug}")
    branch = run(["git", "branch", "--show-current"], worktree).strip()
    number = scenario.pr_state(branch)["number"]
    scenario.step("review")
    sandbox.script_review([])
    scenario.worker("review", number)
    scenario.step("hosted finalize and queue merge")
    scenario.expect_merged(branch)
    scenario.step("final state")
    scenario.expect_on_main(f"fixture/{slug}.txt", slug)


SCENARIOS: dict[str, Callable[[Scenario], None]] = {
    "quick-task": scenario_quick_task, "managed-task": scenario_managed_task,
    "red-ci": scenario_red_ci, "conflict": scenario_conflict,
}


def resolve_head(value: str) -> str:
    head = run(["git", "rev-parse", "--verify", f"{value}^{{commit}}"], SOURCE_ROOT).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise SandboxError(f"{value} is not a commit")
    return head


def run_scenarios(sandbox: Sandbox, selected: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name in selected:
        scenario = Scenario(name, sandbox)
        started = time.monotonic()
        try:
            SCENARIOS[name](scenario)
        except StepFailure as failure:
            outcome = {"result": "failed", "step": failure.step, "observed": failure.observed}
        except SandboxError as error:
            outcome = {"result": "failed", "step": scenario.current, "observed": str(error)}
        else:
            outcome = {"result": "passed"}
        results.append({"scenario": name, **outcome, "seconds": round(time.monotonic() - started)})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "reset"))
    parser.add_argument("--workdir", required=True, type=Path, help="runner-owned directory; its content is replaced")
    parser.add_argument("--head", default="HEAD", help="platform commit to install (default: this checkout's HEAD)")
    parser.add_argument("--scenario", action="append", choices=sorted(SCENARIOS), help="repeatable; default: all")
    args = parser.parse_args()
    config = load_config()
    try:
        check_target(config)
        check_owner_setup(config)
        sandbox = Sandbox(config, args.workdir, resolve_head(args.head))
        lock = Lock(config)
        lock.acquire()
        try:
            sandbox.reset()
            if args.command == "reset":
                return 0
            results = run_scenarios(sandbox, args.scenario or sorted(SCENARIOS))
        finally:
            lock.release()
    except SandboxError as error:
        print(f"live scenarios: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"head": sandbox.head, "results": results}, indent=2))
    print(f"receipt: {live_scenario_gate.write_receipt(SOURCE_ROOT, sandbox.head, results)}")
    return 1 if any(item["result"] != "passed" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
