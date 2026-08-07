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

        project_rules = target / "docs" / "engineering" / "project-rules.md"
        sentinel = "\n<!-- project-owned-upgrade-sentinel -->\n"
        project_rules.write_text(project_rules.read_text(encoding="utf-8") + sentinel, encoding="utf-8")
        local_doc = target / "docs" / "engineering" / "local-only.md"
        local_doc.write_text("# Local-only project documentation\n", encoding="utf-8")
        run(["git", "add", "-A"], target)
        run(["git", "commit", "-m", "Add project-owned customizations"], target)

        run(["copier", "update", "--trust", "--defaults", "--vcs-ref", "HEAD", "--conflict", "inline"], target)

        if "project-owned-upgrade-sentinel" not in project_rules.read_text(encoding="utf-8"):
            raise SystemExit("Copier update removed project-owned project-rules content")
        if not local_doc.exists():
            raise SystemExit("Copier update removed project-owned local-only documentation")
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
