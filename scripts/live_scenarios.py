#!/usr/bin/env python3
"""Run lifecycle scenarios on the real GitHub sandbox repository.

The runner acts as developer and coordinator through documented platform entrypoints only.
It never edits labels, lifecycle comments or queue records. See docs/engineering/live-scenarios.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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

SOURCE_ROOT = Path(__file__).resolve().parents[1]
SANDBOX_DIR = SOURCE_ROOT / "dev-platform" / "live-sandbox"
HEAD_MARKER = Path("dev-platform") / "live-sandbox-head.txt"
WORKDIR_MARKER = ".live-sandbox-workdir"
LOCK_VARIABLE = "LIVE_SCENARIO_LOCK"
LOCK_LEASE_SECONDS = 3 * 3600
POLL_SECONDS = 15
QUEUED = "Publication queued; rerun finish after GitHub reports the exact PR MERGED."
TOKEN_ANCHOR = "permission-pull-requests: write"
OWNER_SECRET = "DEV_PLATFORM_APP_PRIVATE_KEY"
OWNER_VARIABLE = "DEV_PLATFORM_APP_CLIENT_ID"


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


def load_config(path: Path = SANDBOX_DIR / "sandbox.toml") -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    try:
        return Config(data["repository"], data["coordinator_app"], data["coordinator_app_id"], data["required_check"],
                      data["hosted_kinds"], tuple(data["kept_workflows"]), tuple(data["dropped_paths"]),
                      tuple(data["token_read_permissions"]))
    except KeyError as missing:
        raise SandboxError(f"{path} lacks required key {missing}") from missing


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None, *, input_text: str | None = None) -> str:
    """Run one command; a failure names the command and its output, which never holds a token."""
    done = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False, input=input_text,
                          stdin=None if input_text is not None else subprocess.DEVNULL)
    if done.returncode:
        detail = (done.stderr.strip() or done.stdout.strip())[-2000:]
        raise SandboxError(f"{' '.join(command[:4])} exited {done.returncode}: {detail}")
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
    overlay = (source / "dev-platform" / "live-sandbox" / "overlay")
    shutil.copytree(overlay, destination, dirs_exist_ok=True)
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
            f'project_label = "project:dev-platform-sandbox"\ndefault_priority = "P2"\nproject_owner = "{owner}"\n'
            f'\n[agent_sessions]\ndirectory = "{self.workdir / "agent-sessions"}"\nstale_after_seconds = 21600\nended_keep_seconds = 86400\n',
            encoding="utf-8")
        with (self.checkout / ".git" / "info" / "exclude").open("a", encoding="utf-8") as handle:
            handle.write(".dev-platform.toml\n.claude/\n")

    def apply_settings(self) -> None:
        """Idempotent repository settings matching production main, plus the admin path of the baseline write."""
        repo, config = self.config.repository, self.config
        current = gh_json(["api", f"repos/{repo}"], SOURCE_ROOT)
        if not current["allow_squash_merge"] or current["delete_branch_on_merge"]:
            run(["gh", "api", "-X", "PATCH", f"repos/{repo}", "-F", "allow_squash_merge=true", "-F", "delete_branch_on_merge=false",
                 "--jq", ".name"], SOURCE_ROOT)
        run(["gh", "variable", "set", "DEV_PLATFORM_HOSTED_KINDS", "--repo", repo, "--body", config.hosted_kinds], SOURCE_ROOT)
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
            if QUEUED not in str(error):
                raise self.fail(str(error)) from error
        else:
            raise self.fail("finish returned without queueing the PR")

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


def scenario_quick_task(scenario: Scenario) -> None:
    sandbox = scenario.sandbox
    slug = f"quick-{uuid.uuid4().hex[:8]}"
    scenario.step("start")
    output = scenario.platform("dogfood_task.py", "start", slug, "--task", "Live scenario quick task")
    worktree = sandbox.checkout / ".claude" / "worktrees" / slug
    if not worktree.is_dir():
        raise scenario.fail(f"no task worktree after start: {output[-500:]}")
    scenario.step("change")
    (worktree / "fixture" / f"{slug}.txt").write_text(slug + "\n", encoding="utf-8")
    run(["git", "add", "-A"], worktree)
    run(["git", "commit", "-q", "-m", f"Add {slug}"], worktree)
    scenario.step("friction checkpoint")
    scenario.platform("agent_friction.py", "checkpoint", "--result", "none", "--review-note", "Live scenario", cwd=worktree)
    scenario.step("finish")
    branch = run(["git", "branch", "--show-current"], worktree).strip()
    scenario.finish_until_queued(worktree, f"Quick {slug}")
    scenario.step("queue merges")
    final = scenario.wait(lambda: scenario.pr_state(branch), lambda pr: pr.get("state") == "MERGED", 900)
    scenario.step("finish after merge")
    scenario.platform("dogfood_task.py", "finish", cwd=worktree)
    scenario.step("final state")
    merger = (final.get("mergedBy") or {}).get("login", "")
    if sandbox.config.coordinator_app not in merger:
        raise scenario.fail(f"merged by {merger!r}, not the coordinator App")
    content = gh_json(["api", f"repos/{sandbox.config.repository}/contents/fixture/{slug}.txt?ref=main"], SOURCE_ROOT)
    if not content.get("sha"):
        raise scenario.fail("the change is not on main")


SCENARIOS: dict[str, Callable[[Scenario], None]] = {"quick-task": scenario_quick_task}


def resolve_head(value: str) -> str:
    head = run(["git", "rev-parse", "--verify", f"{value}^{{commit}}"], SOURCE_ROOT).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise SandboxError(f"{value} is not a commit")
    return head


def run_scenarios(sandbox: Sandbox, selected: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for name in selected:
        try:
            SCENARIOS[name](Scenario(name, sandbox))
        except StepFailure as failure:
            results.append({"scenario": name, "result": "failed", "step": failure.step, "observed": failure.observed})
        else:
            results.append({"scenario": name, "result": "passed"})
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
    return 1 if any(item["result"] != "passed" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
