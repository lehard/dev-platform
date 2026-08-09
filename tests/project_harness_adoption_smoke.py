from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path, *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, check=True, capture_output=capture)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dev-platform-project-harness-") as tmp:
        target = Path(tmp) / "project"
        target.mkdir()
        run(["git", "init", "-b", "main"], target)
        run(["git", "config", "user.name", "dev-platform-ci"], target)
        run(["git", "config", "user.email", "dev-platform-ci@example.invalid"], target)

        preserved = {
            "AGENTS.md": "# mature project agent contract\n",
            "CLAUDE.md": "# mature project claude contract\n",
            ".gitignore": ".claude/agents-board.json\n.claude/skills/local-only/\nAGENTS.local.md\n",
            "docs/engineering/openspec-workflow.md": "# mature project OpenSpec workflow\n",
            "openspec/config.yaml": "schema: spec-driven\n",
            "scripts/agent_board.py": "# mature agent board\n",
            "scripts/agent_friction.py": "# mature friction loop\n",
            "scripts/merge_to_main.py": "# mature merge serializer\n",
            "scripts/select_checks.py": "# project selector intentionally has no --execute/--full contract\n",
            "scripts/start_worktree.py": "# mature worktree launcher\n",
            "scripts/worktree_cleanup.py": "# mature worktree cleanup\n",
            ".github/workflows/ci.yml": "name: Mature Project CI\n",
        }
        for relative, content in preserved.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        run(
            [
                "copier", "copy", "--trust", "--defaults", "--vcs-ref", "HEAD",
                "--data", "project_name=Mature Project",
                "--data", "project_slug=mature-project",
                "--data", "project_description=Existing project harness adoption smoke",
                "--data", "workflow_profile=multi-agent",
                "--data", "harness_mode=project",
                "--data", "publish_mode=pr",
                str(ROOT), str(target),
            ],
            ROOT,
        )

        for relative, expected in preserved.items():
            actual = (target / relative).read_text(encoding="utf-8")
            if actual != expected:
                raise SystemExit(f"Project-owned file was overwritten during adoption: {relative}")

        platform_workflow = target / ".github" / "workflows" / "dev-platform.yml"
        if not platform_workflow.is_file():
            raise SystemExit("Platform CI was not added under the non-colliding dev-platform.yml name")
        workflow_text = platform_workflow.read_text(encoding="utf-8")
        if "scripts/select_checks.py" in workflow_text:
            raise SystemExit("Project-harness platform CI must not execute or depend on the project selector")
        if "scripts/platform_doctor.py" not in workflow_text:
            raise SystemExit("Project-harness platform CI must still validate the platform contract")

        config = (target / ".dev-platform.toml").read_text(encoding="utf-8")
        if 'harness_mode = "project"' not in config:
            raise SystemExit("Rendered project config did not record harness_mode=project")
        if "platform_git_lifecycle = false" not in config:
            raise SystemExit("Project-owned harness must disable platform Git lifecycle ownership")

        run(["git", "add", "-A"], target)
        run(["git", "commit", "-m", "Adopt dev-platform without replacing mature harness"], target)
        run(["python3", "-m", "compileall", "-q", "scripts"], target)
        doctor = subprocess.run(["python3", "scripts/platform_doctor.py"], cwd=target, text=True)
        if doctor.returncode != 0:
            raise SystemExit(doctor.returncode)
        print("Project-owned harness adoption smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
