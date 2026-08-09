from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADOPT_PATH = ROOT / "scripts" / "adopt_project.py"
SPEC = importlib.util.spec_from_file_location("adopt_project", ADOPT_PATH)
assert SPEC and SPEC.loader
adopt_project = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adopt_project)


def run(
    command: list[str], cwd: Path, *, capture: bool = False, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, check=True, capture_output=capture, env=env)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dev-platform-project-harness-") as tmp:
        temp_root = Path(tmp)
        target = temp_root / "project"
        target.mkdir()
        run(["git", "init", "-b", "main"], target)
        run(["git", "config", "user.name", "dev-platform-ci"], target)
        run(["git", "config", "user.email", "dev-platform-ci@example.invalid"], target)

        preserved = {
            "AGENTS.md": "# mature project agent contract\n",
            "CLAUDE.md": "# mature project claude contract\n",
            ".gitignore": ".claude/\n.codex/\nAGENTS.local.md\n",
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

        kind, reasons = adopt_project.classify_repository(target)
        plan = adopt_project.plan_adoption(target, kind, reasons)
        if kind != "existing":
            raise SystemExit(f"Expected existing repository, got {kind}")
        expected_plan = ("multi-agent", "project", "pr")
        actual_plan = (plan["workflow_profile"], plan["harness_mode"], plan["publish_mode"])
        if actual_plan != expected_plan:
            raise SystemExit(f"Unexpected mature adoption plan: {actual_plan!r}")
        if plan["blockers"]:
            raise SystemExit("Coherent mature project harness must not be blocked: " + "; ".join(plan["blockers"]))
        if not any("coherent project-owned harness" in reason for reason in plan["reasons"]):
            raise SystemExit("Mature adoption plan is missing auditable harness detection reason")
        if not any("multi-agent coordination" in reason for reason in plan["reasons"]):
            raise SystemExit("Mature adoption plan is missing auditable multi-agent detection reason")

        run(
            [
                "copier", "copy", "--trust", "--defaults", "--vcs-ref", "HEAD",
                "--data", "project_name=Mature Project",
                "--data", "project_slug=mature-project",
                "--data", "project_description=Existing project harness adoption smoke",
                "--data", f"workflow_profile={plan['workflow_profile']}",
                "--data", f"harness_mode={plan['harness_mode']}",
                "--data", f"publish_mode={plan['publish_mode']}",
                str(ROOT), str(target),
            ],
            ROOT,
        )
        adopt_project.configure_project_required_files(target, list(plan["project_required_files"]))

        for relative, expected in preserved.items():
            actual = (target / relative).read_text(encoding="utf-8")
            if actual != expected:
                raise SystemExit(f"Project-owned file was overwritten during adoption: {relative}")

        platform_workflow = target / ".github" / "workflows" / "dev-platform.yml"
        if not platform_workflow.is_file():
            raise SystemExit("Platform CI was not added under the non-colliding dev-platform.yml name")
        workflow_text = platform_workflow.read_text(encoding="utf-8")
        if not workflow_text.endswith("\n") or workflow_text.endswith("\n\n"):
            raise SystemExit("Rendered Dev Platform workflow must end with exactly one newline")
        if "scripts/select_checks.py" in workflow_text or "--execute" in workflow_text or "--full" in workflow_text:
            raise SystemExit("Project-harness platform CI must not execute or depend on the project selector")
        for required_hygiene in (
            "scripts/platform_doctor.py",
            "scripts/openspec_lifecycle.py check",
            "openspec@1.6.0 validate --all --strict --no-interactive",
        ):
            if required_hygiene not in workflow_text:
                raise SystemExit(f"Project-harness platform CI is missing shared hygiene: {required_hygiene}")
        if "pip install" in workflow_text or "npm ci" in workflow_text:
            raise SystemExit("Project-harness platform CI must not install arbitrary product dependencies")

        config_path = target / ".dev-platform.toml"
        config = config_path.read_text(encoding="utf-8")
        if 'harness_mode = "project"' not in config:
            raise SystemExit("Rendered project config did not record harness_mode=project")
        if 'workflow_profile = "multi-agent"' not in config:
            raise SystemExit("Rendered project config did not record workflow_profile=multi-agent")
        if 'publish_mode = "pr"' not in config:
            raise SystemExit("Rendered project config did not record publish_mode=pr")
        if "platform_git_lifecycle = false" not in config:
            raise SystemExit("Project-owned harness must disable platform Git lifecycle ownership")
        for required_file in plan["project_required_files"]:
            if f'"{required_file}"' not in config:
                raise SystemExit(f"Project-owned lifecycle requirement was not recorded: {required_file}")

        central_workflow = (ROOT / ".github" / "workflows" / "adopt-project.yml").read_text(encoding="utf-8")
        if "steps.adopt.outputs.kind == 'fresh'" not in central_workflow:
            raise SystemExit("Fresh-only auto-merge guard is missing from one-command onboarding")
        if "steps.adopt.outputs.kind == 'fresh' || steps.adopt.outputs.status == 'already_adopted'" not in central_workflow:
            raise SystemExit("Managed promotion must exclude first-pass existing migrations")
        if "Product/application checks remain owned by the repository CI" not in central_workflow:
            raise SystemExit("Existing project-harness PR must explain delegated product validation")
        if "Product/application validation is delegated to the repository-owned CI." not in central_workflow:
            raise SystemExit("Workflow summary must explain delegated product validation")

        run(["git", "add", "-A"], target)
        run(["git", "commit", "-m", "Adopt dev-platform without replacing mature harness"], target)

        origin = temp_root / "origin.git"
        run(["git", "init", "--bare", str(origin)], temp_root)
        run(["git", "remote", "add", "origin", str(origin)], target)
        run(["git", "push", "-u", "origin", "main"], target)

        fake_bin = temp_root / "bin"
        fake_bin.mkdir()
        fake_openspec = fake_bin / "openspec"
        fake_openspec.write_text(
            "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo '1.6.0'; exit 0; fi\nexit 0\n",
            encoding="utf-8",
        )
        fake_openspec.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

        lifecycle_before = {relative: (target / relative).read_bytes() for relative in preserved}
        run(["python3", "scripts/dev.py", "ready"], target, env=env)
        run(["python3", "scripts/dev.py", "ready"], target, env=env)
        for relative, expected in lifecycle_before.items():
            if (target / relative).read_bytes() != expected:
                raise SystemExit(f"dev.py ready mutated project-owned lifecycle file: {relative}")

        run(["python3", "-m", "compileall", "-q", "scripts"], target)
        doctor = subprocess.run(["python3", "scripts/platform_doctor.py"], cwd=target, text=True, env=env)
        if doctor.returncode != 0:
            raise SystemExit(doctor.returncode)
        print("Project-owned mature multi-agent adoption acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
