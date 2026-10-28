"""Downstream smoke: the supported reconcile passes the doctor-installed merge-commit hook.

Renders the committed template as a multi-agent project, lets ``agent_doctor.py``
install the platform git hooks exactly as a downstream project gets them, and
then proves on that project: ``finish_task.py --reconcile`` merges an advanced
``origin/main`` into a diverged task worktree without any override and leaves no
intent behind; an ad-hoc merge in the task worktree and a merge in the
integration copy stay blocked; the task branch is not pushed and ``origin/main``
is untouched.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTENT = "dev-platform-reconcile-merge"


def run(command: list[str], cwd: Path, *, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if check and done.returncode != 0:
        raise SystemExit(f"{' '.join(command)} failed in {cwd} (exit {done.returncode}):\n{done.stdout}\n{done.stderr}")
    return done


def git(cwd: Path, *args: str, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd, check=check, env=env)


def commit(cwd: Path, name: str, env: dict[str, str] | None = None) -> str:
    (cwd / name).write_text(name + "\n", encoding="utf-8")
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", name, env=env)
    return git(cwd, "rev-parse", "HEAD").stdout.strip()


def refused(cwd: Path, ref: str, message: str) -> None:
    before = git(cwd, "rev-parse", "HEAD").stdout
    merged = git(cwd, "merge", "--no-edit", ref, check=False)
    if merged.returncode == 0 or message not in merged.stderr:
        raise SystemExit(f"merge of {ref} in {cwd} was not refused with {message!r}:\n{merged.stdout}\n{merged.stderr}")
    if git(cwd, "rev-parse", "HEAD").stdout != before:
        raise SystemExit(f"a merge commit was created in {cwd} despite the hook")
    git(cwd, "merge", "--abort", check=False)


def main() -> int:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="dev-platform-reconcile-hook-") as tmp:
        base = Path(tmp)
        project = base / "project"
        operator = base / "operator.toml"
        operator.write_text("# synthetic operator config fixture\n", encoding="utf-8")
        run(["copier", "copy", "--trust", "--defaults", "--vcs-ref", "HEAD",
             "--data", "project_name=Reconcile Hook", "--data", "project_slug=reconcile-hook",
             "--data", "project_description=Reconcile hook smoke", "--data", "workflow_profile=multi-agent",
             "--data", "publish_mode=pr", "--data", f"operator_config_path={operator}",
             str(ROOT), str(project)], ROOT)
        if not (project / ".git").is_dir():
            git(project, "init", "-q", "-b", "main")
        for name, value in (("user.name", "dev-platform-ci"), ("user.email", "dev-platform-ci@example.invalid")):
            git(project, "config", name, value)
        git(project, "add", "-A")
        git(project, "commit", "-q", "-m", "Generated project")
        origin = base / "origin.git"
        git(base, "init", "-q", "--bare", str(origin))
        git(project, "remote", "add", "origin", str(origin))
        git(project, "push", "-q", "-u", "origin", "main")

        run(["python3", "scripts/agent_doctor.py", "--no-fetch"], project, check=False)
        hook = project / ".git" / "hooks" / "pre-merge-commit"
        if hook.read_bytes() != (project / "scripts" / "git_hooks" / "pre-merge-commit").read_bytes():
            raise SystemExit("agent_doctor did not install the platform pre-merge-commit hook")

        task = base / "task"
        git(project, "worktree", "add", "-q", "-b", "agent/smoke-task", str(task))
        task_head = commit(task, "task-change.txt")
        other = base / "other"
        git(base, "clone", "-q", str(origin), str(other))
        for name, value in (("user.name", "other"), ("user.email", "other@example.invalid")):
            git(other, "config", name, value)
        commit(other, "main-change.txt")
        git(other, "push", "-q")
        main_after = git(other, "rev-parse", "HEAD").stdout.strip()

        # Without the reconcile, the same merge stays blocked (lehard/dev-platform#420 shape).
        git(task, "fetch", "-q", "origin")
        refused(task, "origin/main", "merge commits in task worktrees are blocked")

        reconciled = run(["python3", "scripts/finish_task.py", "--reconcile"], task, check=False)
        if reconciled.returncode != 0:
            raise SystemExit(f"finish_task.py --reconcile failed:\n{reconciled.stdout}\n{reconciled.stderr}")
        parents = git(task, "rev-list", "--parents", "-n", "1", "HEAD").stdout.split()[1:]
        if sorted(parents) != sorted([task_head, main_after]):
            raise SystemExit(f"reconcile did not create the merge of {task_head} and {main_after}: parents {parents}")
        git_dir = Path(git(task, "rev-parse", "--path-format=absolute", "--git-dir").stdout.strip())
        if (git_dir / INTENT).exists():
            raise SystemExit("the reconcile intent outlived its merge")

        later = commit(other, "later-change.txt")
        git(other, "push", "-q")
        git(task, "fetch", "-q", "origin")
        refused(task, "origin/main", "merge commits in task worktrees are blocked")

        # Diverging the integration copy needs the platform's own explicit pre-commit override.
        allow_main_commit = {**os.environ, "DEV_PLATFORM_ALLOW_MAIN_COMMIT": "1"}
        git(project, "checkout", "-q", "-b", "topic")
        commit(project, "topic-change.txt", env=allow_main_commit)
        git(project, "checkout", "-q", "main")
        commit(project, "integration-change.txt", env=allow_main_commit)
        refused(project, "topic", "merge commits in the integration copy are blocked")

        if git(base, "--git-dir", str(origin), "rev-parse", "main").stdout.strip() != later:
            raise SystemExit("origin/main was changed by the smoke")
        if git(base, "--git-dir", str(origin), "show-ref", "--verify", "--quiet", "refs/heads/agent/smoke-task", check=False).returncode == 0:
            raise SystemExit("the unpublished task branch was pushed")
    print("reconcile merge hook smoke: reconcile admitted; ad-hoc task merge, integration-copy merge refused; no push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
