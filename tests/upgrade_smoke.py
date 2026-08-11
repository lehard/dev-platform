from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FALLBACK_BASE_REF = "cb46d0c787334c473f8e8c46f018ca14e665c507"


def run(command: list[str], cwd: Path, *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, check=True, capture_output=capture)


def choose_base_ref() -> str:
    explicit = os.environ.get("UPGRADE_BASE_REF")
    if explicit:
        return explicit
    result = subprocess.run(
        ["git", "tag", "--list", "v[0-9]*", "--sort=-v:refname"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    tags = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return tags[0] if tags else FALLBACK_BASE_REF


def append_sentinel(path: Path, sentinel: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + f"\n{sentinel}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a Copier upgrade from the last stable platform version to HEAD.")
    parser.add_argument("--profile", choices=["light", "standard", "multi-agent"], required=True)
    parser.add_argument("--publish-mode", choices=["direct", "pr"], required=True)
    args = parser.parse_args()

    base_ref = choose_base_ref()
    with tempfile.TemporaryDirectory(prefix=f"dev-platform-upgrade-{args.profile}-") as tmp:
        target = Path(tmp) / "project"
        run(
            [
                "copier", "copy", "--trust", "--defaults", "--vcs-ref", base_ref,
                "--data", f"project_name=Upgrade {args.profile}",
                "--data", f"project_slug=upgrade-{args.profile}",
                "--data", f"project_description=Upgrade smoke {args.profile}",
                "--data", f"workflow_profile={args.profile}",
                "--data", f"publish_mode={args.publish_mode}",
                str(ROOT), str(target),
            ],
            ROOT,
        )

        run(["git", "config", "user.name", "dev-platform-ci"], target)
        run(["git", "config", "user.email", "dev-platform-ci@example.invalid"], target)
        run(["git", "add", "-A"], target)
        run(["git", "commit", "-m", "Baseline generated project"], target)

        sentinels = {
            ".dev-platform.toml": "# project-owned-platform-config-sentinel",
            "AGENTS.md": "<!-- project-owned-agents-sentinel -->",
            "CLAUDE.md": "<!-- project-owned-claude-sentinel -->",
            "README.md": "<!-- project-owned-readme-sentinel -->",
            "dev-platform/checks.toml": "# project-owned-checks-sentinel",
            "openspec/config.yaml": "# project-owned-openspec-sentinel",
            "docs/engineering/project-rules.md": "<!-- project-owned-rules-sentinel -->",
        }
        for relative, sentinel in sentinels.items():
            append_sentinel(target / relative, sentinel)

        platform_config = target / ".dev-platform.toml"
        config_text = platform_config.read_text(encoding="utf-8")
        if "project_required_files = []" in config_text:
            config_text = config_text.replace(
                "project_required_files = []",
                'project_required_files = ["scripts/project_required_helper.py"]',
                1,
            )
            platform_config.write_text(config_text, encoding="utf-8")
            (target / "scripts" / "project_required_helper.py").write_text("# project-owned helper\n", encoding="utf-8")

        local_doc = target / "docs" / "engineering" / "local-only.md"
        local_doc.write_text("# Local-only project documentation\n", encoding="utf-8")
        run(["git", "add", "-A"], target)
        run(["git", "commit", "-m", "Add project-owned customizations"], target)

        run(["copier", "update", "--trust", "--defaults", "--vcs-ref", "HEAD", "--conflict", "inline"], target)

        for relative, sentinel in sentinels.items():
            if sentinel not in (target / relative).read_text(encoding="utf-8"):
                raise SystemExit(f"Copier update removed project-owned content from {relative}")
        if 'project_required_files = ["scripts/project_required_helper.py"]' not in platform_config.read_text(encoding="utf-8"):
            raise SystemExit("Copier update removed project-owned platform configuration")
        if not local_doc.exists():
            raise SystemExit("Copier update removed project-owned local-only documentation")
        if not (target / ".github" / "workflows" / "dev-platform.yml").is_file():
            raise SystemExit("Copier update did not migrate platform CI to .github/workflows/dev-platform.yml")
        if not (target / "scripts" / "managed_task.py").is_file():
            raise SystemExit("Copier update did not materialize managed-task intake")
        if not (target / "scripts" / "start_managed_task.py").is_file():
            raise SystemExit("Copier update did not materialize managed-task start")
        if list(target.rglob("*.rej")):
            raise SystemExit("Copier update left .rej files")

        run(["python3", "-m", "compileall", "-q", "scripts"], target)
        doctor = subprocess.run(["python3", "scripts/platform_doctor.py"], cwd=target, text=True)
        if doctor.returncode != 0:
            raise SystemExit(doctor.returncode)

        status = run(["git", "status", "--porcelain"], target, capture=True).stdout
        print(f"Upgrade smoke passed: base={base_ref} profile={args.profile} publish={args.publish_mode}")
        if status.strip():
            print("Expected post-update diff is present and reviewable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
