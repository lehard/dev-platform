from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_TAG = "v99.99.99"
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_project  # noqa: E402


def run(command: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=check)


def append_answer(path: Path, key: str, value: str) -> None:
    text = path.read_text(encoding="utf-8").rstrip() + "\n"
    if f"{key}:" not in text:
        text += f"{key}: {value}\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    existing = run(["git", "show-ref", "--verify", "--quiet", f"refs/tags/{TARGET_TAG}"], ROOT, check=False)
    if existing.returncode == 0:
        raise SystemExit(f"Local smoke-test tag already exists: {TARGET_TAG}")
    run(["git", "tag", TARGET_TAG, "HEAD"], ROOT)
    try:
        with tempfile.TemporaryDirectory(prefix="dev-platform-recopy-smoke-") as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            run(["git", "init", "-b", "main"], project)
            run(["git", "config", "user.name", "Rollout Smoke"], project)
            run(["git", "config", "user.email", "rollout-smoke@example.invalid"], project)

            run(
                [
                    "copier",
                    "copy",
                    "--trust",
                    "--defaults",
                    "--vcs-ref",
                    "v1.2.3",
                    "--data",
                    "project_name=Transition Smoke",
                    "--data",
                    "project_slug=transition-smoke",
                    "--data",
                    "project_description=Reproduce project-owned harness transition",
                    "--data",
                    "workflow_profile=standard",
                    "--data",
                    "publish_mode=direct",
                    str(ROOT),
                    str(project),
                ],
                ROOT,
            )

            custom_scripts = {
                "scripts/agent_doctor.py": "#!/usr/bin/env python3\nprint('project-owned doctor sentinel')\n",
                "scripts/agent_friction.py": "#!/usr/bin/env python3\nprint('project-owned friction sentinel')\n",
                "scripts/finish_task.py": "#!/usr/bin/env python3\nprint('project-owned finish sentinel')\n",
                "scripts/project_publish.py": "#!/usr/bin/env python3\nprint('project-owned publish sentinel')\n",
                "scripts/project_sync.py": "#!/usr/bin/env python3\nprint('project-owned sync sentinel')\n",
                "scripts/select_checks.py": "#!/usr/bin/env python3\nprint('project-owned checks sentinel')\n",
                "scripts/start_task.py": "#!/usr/bin/env python3\nprint('project-owned start sentinel')\n",
            }
            for relative, body in custom_scripts.items():
                (project / relative).write_text(body, encoding="utf-8")

            answers_path = project / ".copier-answers.yml"
            append_answer(answers_path, "harness_mode", "project")
            config_path = project / ".dev-platform.toml"
            config_text = config_path.read_text(encoding="utf-8")
            if "harness_mode" not in config_text:
                config_text = config_text.replace(
                    'workflow_profile = "standard"\n',
                    'workflow_profile = "standard"\nharness_mode = "project"\n',
                    1,
                )
            if "platform_git_lifecycle" not in config_text:
                marker = "[capabilities]\n"
                config_text = config_text.replace(
                    marker,
                    marker + "platform_git_lifecycle = false\n",
                    1,
                )
            config_path.write_text(config_text, encoding="utf-8")

            product_ci = project / ".github" / "workflows" / "ci.yml"
            product_ci.parent.mkdir(parents=True, exist_ok=True)
            product_ci.write_text("name: Project-owned product CI\n", encoding="utf-8")

            run(["git", "add", "-A"], project)
            run(["git", "commit", "-m", "Simulate customized v1.2.3 project harness"], project)

            before = rollout_project.snapshot_existing_project_owned(project)
            config_before = rollout_project.platform_config_contract(project)
            strategy = rollout_project.copier_update_with_guarded_recopy(
                project,
                TARGET_TAG,
                env=os.environ.copy(),
            )
            if strategy != "guarded-recopy":
                raise SystemExit(f"Expected guarded-recopy transition, got {strategy}")

            rollout_project.normalize_copier_answers(project)
            after_answers = rollout_project.parse_answers(answers_path.read_text(encoding="utf-8"))
            if after_answers.get("_commit") != TARGET_TAG:
                raise SystemExit(f"Copier did not record {TARGET_TAG}: {after_answers.get('_commit')}")
            if rollout_project.load_platform_version(project) != TARGET_TAG[1:]:
                raise SystemExit("platform_bootstrap did not synchronize platform_version to current smoke tag")
            if rollout_project.platform_config_contract(project) != config_before:
                raise SystemExit("Project config changed beyond platform_version")
            rollout_project.require_project_owned_snapshot(project, before)
            if not (project / ".github" / "workflows" / "dev-platform.yml").exists():
                raise SystemExit("Guarded recopy did not add the non-colliding platform CI workflow")
            if rollout_project.find_reject_files(project):
                raise SystemExit("Guarded recopy left .rej files")

            print("Guarded project-harness recopy transition smoke passed.")
    finally:
        run(["git", "tag", "-d", TARGET_TAG], ROOT, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
