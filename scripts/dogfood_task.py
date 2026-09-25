#!/usr/bin/env python3
"""Central dev-platform task lifecycle adapter.

Managed backlog intake first materializes one untracked OpenSpec package in
the integration checkout.  ``start --change`` transfers only that validated
package into the newly created isolated worktree, leaving main clean before
implementation begins.  Status and finish delegate to the shared
GitHub-backed lifecycle; they never invent a second publication state model.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


CHANGE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CODEX_EXECUTOR_PROMPT = (
    "You are the delegated Codex executor for this managed dev-platform task. "
    "Read the materialized canonical OpenSpec and relevant current repository context, "
    "implement only the bounded task scope in this assigned worktree, and return the exact "
    "diff, checks run, uncertainty, and any escalation trigger to the Sol supervisor."
)


def bounded_executor_prompt(root: Path, fallback: str) -> str:
    """Point a child at its derived Requirement context without inlining it."""
    state_path = root / ".managed-task-state.json"
    if not state_path.is_file():
        return fallback
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        change = state["change"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SystemExit(f"Managed task identity is unreadable before routing: {exc}") from exc
    if not isinstance(change, str) or not CHANGE_RE.fullmatch(change):
        raise SystemExit("Managed task identity has an invalid change before routing.")
    path = root / ".claude" / "requirement-child-context" / f"{change}.json"
    if not path.is_file():
        return fallback
    try:
        context = json.loads(path.read_text(encoding="utf-8"))
        package_path = (root / context["managed_package"]).resolve()
        if not package_path.is_relative_to(root.resolve() / "openspec" / "changes"):
            raise SystemExit("Bounded Requirement context points outside canonical OpenSpec changes.")
        provenance = package_path / ".managed-task.json"
        import hashlib
        observed_digest = hashlib.sha256(provenance.read_bytes()).hexdigest()
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SystemExit(f"Bounded Requirement context is unreadable before routing: {exc}") from exc
    if (context.get("source_issue") != state.get("source_issue") or context.get("change") != change
            or context.get("repository_head") != git(root, "rev-parse", "HEAD")
            or context.get("managed_provenance_sha256") != observed_digest):
        raise SystemExit("Bounded Requirement context is stale before routing; resume the exact managed child to refresh it.")
    return fallback + f" Read the bounded Requirement child context at {path} before implementation."


def run(command: list[str], root: Path) -> None:
    result = subprocess.run(command, cwd=root)
    if result.returncode:
        raise SystemExit(result.returncode)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def integration_root(cwd: Path) -> Path:
    root = Path(git(cwd, "rev-parse", "--show-toplevel")).resolve()
    common = Path(git(root, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (root / common).resolve()
    integration = common.parent
    if root != integration:
        raise SystemExit("Central start must run from the integration checkout, not an existing task worktree.")
    if git(root, "branch", "--show-current") != "main":
        raise SystemExit("Central start requires the integration checkout to have main checked out.")
    return root


def managed_change(root: Path, change: str) -> Path:
    if not CHANGE_RE.fullmatch(change):
        raise SystemExit("--change must be a lowercase OpenSpec change name.")
    path = root / "openspec" / "changes" / change
    provenance = path / ".managed-task.json"
    if not path.is_dir() or not provenance.is_file():
        raise SystemExit(f"Managed OpenSpec package not found: {path}")
    try:
        payload = json.loads(provenance.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Managed OpenSpec provenance is invalid: {exc}") from exc
    identity = payload.get("source_issue") or payload.get("private_lineage_handle")
    if payload.get("change") != change or not isinstance(identity, str) or (
        "source_issue" not in payload and not re.fullmatch(r"pln_[0-9a-f]{32}", identity)
    ):
        raise SystemExit("Managed OpenSpec provenance does not identify this change.")
    return path


def only_pending_change(root: Path, change: str) -> None:
    allowed = f"openspec/changes/{change}/"
    status = git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
    unexpected = [line for line in status if len(line) < 4 or not line[3:].replace("\\", "/").startswith(allowed)]
    if unexpected:
        preview = ", ".join(line[3:] for line in unexpected[:5])
        raise SystemExit(f"Integration copy is dirty outside managed change {change}: {preview}")


def worktree_path(root: Path, slug: str) -> Path:
    # This source-owned config is intentionally required; a fallback default
    # would hide a source/template contract drift.
    import tomllib

    with (root / ".dev-platform.toml").open("rb") as handle:
        config = tomllib.load(handle)
    relative = config.get("paths", {}).get("worktrees")
    if not isinstance(relative, str) or not relative:
        raise SystemExit("Central source configuration is missing paths.worktrees.")
    return (root / relative / slug).resolve()


def verify_source_contract(root: Path) -> None:
    """Fail closed if the explicit source adapter surface is incomplete."""
    import tomllib

    with (root / ".dev-platform.toml").open("rb") as handle:
        config = tomllib.load(handle)
    if config.get("main_branch") != "main" or config.get("workflow_profile") != "multi-agent":
        raise SystemExit("Central source configuration must declare main and the multi-agent workspace profile.")
    if config.get("harness_mode") != "platform" or config.get("publish_mode") != "pr" or config.get("pr_merge_mode") not in {"auto", "manual"}:
        raise SystemExit("Central source configuration must explicitly select the platform PR lifecycle and merge policy.")
    required = config.get("source_required_paths")
    if not isinstance(required, list) or not required or not all(isinstance(path, str) and path for path in required):
        raise SystemExit("Central source configuration is missing source_required_paths.")
    missing = [path for path in required if not (root / path).is_file()]
    if missing:
        raise SystemExit("Central source lifecycle paths are missing: " + ", ".join(missing))


def start(root: Path, args: argparse.Namespace) -> int:
    verify_source_contract(root)
    change_path: Path | None = None
    staged_parent: Path | None = None
    if args.change:
        change_path = managed_change(root, args.change)
        only_pending_change(root, args.change)
        staged_parent = Path(tempfile.mkdtemp(prefix="dev-platform-managed-change-"))
        shutil.move(str(change_path), str(staged_parent / args.change))
    try:
        run(["python3", "scripts/agent_doctor.py"], root)
        run(
            ["python3", "scripts/start_task.py", args.slug, "--task", args.task, "--scope", args.scope],
            root,
        )
        if change_path is not None and staged_parent is not None:
            destination = worktree_path(root, args.slug) / "openspec" / "changes" / args.change
            if destination.exists():
                raise SystemExit(f"Refusing to overwrite OpenSpec package already in task worktree: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_parent / args.change), str(destination))
            print(f"Transferred managed OpenSpec package to: {destination}")
    except BaseException:
        if change_path is not None and staged_parent is not None and (staged_parent / args.change).exists():
            change_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_parent / args.change), str(change_path))
        raise
    finally:
        if staged_parent is not None:
            shutil.rmtree(staged_parent, ignore_errors=True)
    return 0


def current_root() -> Path:
    return Path(git(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()


def status(args: argparse.Namespace) -> int:
    root = current_root()
    verify_source_contract(root)
    command = ["python3", "scripts/finish_task.py", "--status"]
    if getattr(args, "json", False):
        command.append("--json")
    run(command, root)
    return 0


def finish(args: argparse.Namespace) -> int:
    root = current_root()
    verify_source_contract(root)
    require_routing_gate(root)
    command = ["python3", "scripts/finish_task.py", "--cleanup"]
    if args.title:
        command += ["--title", args.title]
    if args.body:
        command += ["--body", args.body]
    run(command, root)
    return 0


def reconcile(_: argparse.Namespace) -> int:
    root = current_root()
    verify_source_contract(root)
    run(["python3", "scripts/finish_task.py", "--reconcile"], root)
    return 0


def require_routing_gate(root: Path) -> None:
    """Verify exact durable route evidence before central terminal delivery."""
    has_state = (root / ".managed-task-state.json").is_file()
    has_active = bool(list((root / "openspec" / "changes").glob("*/.managed-task.json")))
    if not has_state and not has_active:
        return
    module_path = root / "template" / "scripts" / "model_routing.py"
    if not module_path.is_file():
        # Unit/integration harnesses create a temporary managed checkout but
        # exercise this central source adapter.  The source-owned template is
        # still authoritative; it simply lives beside this file, not in the
        # temporary checkout.
        module_path = Path(__file__).resolve().parents[1] / "template" / "scripts" / "model_routing.py"
    if not module_path.is_file():
        raise SystemExit("Dogfood routing gate requires the source-owned template/scripts/model_routing.py implementation.")
    template_scripts = str(module_path.parent)
    if template_scripts not in sys.path:
        sys.path.insert(0, template_scripts)
    spec = importlib.util.spec_from_file_location("_dogfood_model_routing", module_path)
    assert spec and spec.loader
    routing = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = routing
    spec.loader.exec_module(routing)
    try:
        source_issue, change = routing.current_managed_identity(root)
    except routing.RoutingError as exc:
        raise SystemExit(f"Dogfood routing gate cannot establish exact managed task identity: {exc}") from exc
    try:
        routing.require_routing_gate(root, source_issue, change)
    except routing.RoutingError as exc:
        raise SystemExit(
            "Dogfood routing gate blocked publication: " + str(exc) + ". "
            "Routing must be recorded before implementation; archive does not permit retrospective routing."
        ) from exc


def route_codex(args: argparse.Namespace) -> int:
    """Run the mandatory dogfood routing hand-off after supervisor preflight.

    This command is intentionally source-only: it keeps the user entrypoint
    simple while making the supervisor's chosen standard/routine profile launch
    the configured Codex executor through the existing native containment path.
    """
    root = current_root()
    verify_source_contract(root)
    command = ["python3", "scripts/model_routing.py", "dispatch-codex"]
    if args.profile:
        command += ["--profile", args.profile]
    command += [
        "--rationale",
        args.rationale,
        "--prompt",
        bounded_executor_prompt(root, args.prompt or CODEX_EXECUTOR_PROMPT),
    ]
    for item in args.evidence:
        command += ["--evidence", item]
    run(command, root)
    return 0


def route_claude(args: argparse.Namespace) -> int:
    """Run the mandatory dogfood routing hand-off after supervisor preflight.

    Unlike route_codex, this cannot itself launch the child: a native Claude
    Code subagent can only be started by the supervisor's own Agent-tool
    call, in place in the current working directory. This records the route
    and prints the exact hand-off the supervisor must invoke;
    report-claude-execution records the result afterward.
    """
    root = current_root()
    verify_source_contract(root)
    handoff = bounded_executor_prompt(root, "Read the canonical managed OpenSpec before implementation.")
    command = ["python3", "scripts/model_routing.py", "dispatch-claude"]
    if args.profile:
        command += ["--profile", args.profile]
    command += ["--rationale", args.rationale]
    for item in args.evidence:
        command += ["--evidence", item]
    run(command, root)
    if handoff != "Read the canonical managed OpenSpec before implementation.":
        print(f"Bounded child handoff for the native Claude executor: {handoff}")
    return 0


def report_claude_execution(args: argparse.Namespace) -> int:
    """Record that the supervisor actually invoked the Claude hand-off, and verify containment."""
    root = current_root()
    verify_source_contract(root)
    command = [
        "python3",
        "scripts/model_routing.py",
        "record-claude-execution",
        "--agent-id",
        args.agent_id,
    ]
    if args.summary:
        command += ["--summary", args.summary]
    run(command, root)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the supported central dev-platform task lifecycle.")
    sub = parser.add_subparsers(dest="command", required=True)
    start_parser = sub.add_parser("start", help="Prepare an isolated source task worktree.")
    start_parser.add_argument("slug")
    start_parser.add_argument("--task", required=True)
    start_parser.add_argument("--scope", default="")
    start_parser.add_argument("--change", help="Transfer this already-imported managed OpenSpec package into the new worktree.")
    start_parser.set_defaults(func=lambda args: start(integration_root(Path.cwd()), args))
    status_parser = sub.add_parser("status", help="Read the authoritative publication state without mutation.")
    status_parser.add_argument("--json", action="store_true", help="Emit the read-only status payload as JSON.")
    status_parser.set_defaults(func=status)
    finish_parser = sub.add_parser("finish", help="Validate, publish/resume, merge, reconcile, and clean up a source task.")
    finish_parser.add_argument("--title")
    finish_parser.add_argument("--body")
    finish_parser.set_defaults(func=finish)
    reconcile_parser = sub.add_parser("reconcile", help="Safely incorporate current authoritative main before validation.")
    reconcile_parser.set_defaults(func=reconcile)
    route_parser = sub.add_parser(
        "route-codex",
        help="Record the Sol supervisor's semantic route and dispatch routine/standard work.",
    )
    route_parser.add_argument(
        "--profile",
        choices=("routine", "standard", "complex"),
        default=None,
        help="omit to confirm the tier already authored with the managed task (bounded freshness check)",
    )
    route_parser.add_argument("--rationale", required=True)
    route_parser.add_argument("--evidence", action="append", default=[])
    route_parser.add_argument("--prompt")
    route_parser.set_defaults(func=route_codex)
    route_claude_parser = sub.add_parser(
        "route-claude",
        help="Record the strong Claude parent's semantic route for the Claude Code path; prints the hand-off to invoke.",
    )
    route_claude_parser.add_argument(
        "--profile",
        choices=("routine", "standard", "complex"),
        default=None,
        help="omit to confirm the tier already authored with the managed task (bounded freshness check)",
    )
    route_claude_parser.add_argument("--rationale", required=True)
    route_claude_parser.add_argument("--evidence", action="append", default=[])
    route_claude_parser.set_defaults(func=route_claude)
    report_claude_parser = sub.add_parser(
        "report-claude-execution",
        help="Record that the supervisor actually invoked the Claude hand-off, and verify containment.",
    )
    report_claude_parser.add_argument("--agent-id", required=True)
    report_claude_parser.add_argument("--summary")
    report_claude_parser.set_defaults(func=report_claude_execution)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
