from __future__ import annotations

import argparse
import json
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
            ".gitignore": "# project-owned-cuby-ignore-sentinel",
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

        # Cuby-like names with harmless fixture text only. They prove that a
        # platform-harness update keeps the project's effective ignore rules.
        cuby_like_artifacts = {
            ".env": "synthetic environment fixture\n",
            "config/provider-credentials.json": "{\"synthetic\": true}\n",
            "var/app.sqlite3": "synthetic database fixture\n",
            "node_modules/.package-lock.json": "synthetic dependency fixture\n",
            "dist/assets/app.js": "synthetic build fixture\n",
            "tsconfig.tsbuildinfo": "synthetic TypeScript fixture\n",
        }
        gitignore = target / ".gitignore"
        gitignore.write_text(
            gitignore.read_text(encoding="utf-8")
            + "\n# Project-owned Cuby runtime ignores\n"
            + ".env\nconfig/*credentials.json\nvar/*.sqlite3\nnode_modules/\ndist/\n*.tsbuildinfo\n",
            encoding="utf-8",
        )
        for relative, content in cuby_like_artifacts.items():
            artifact = target / relative
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(content, encoding="utf-8")

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
        for relative in cuby_like_artifacts:
            ignored = subprocess.run(
                ["git", "check-ignore", "--quiet", "--no-index", "--", relative],
                cwd=target,
                text=True,
            )
            if ignored.returncode != 0:
                raise SystemExit(f"Copier update removed ignore coverage for {relative}")
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
        if not (target / "scripts" / "managed_project_status.py").is_file():
            raise SystemExit("Copier update did not materialize managed Project status reconciliation")
        if not (target / "scripts" / "model_routing.py").is_file():
            raise SystemExit("Copier update did not materialize provider-local model routing")
        if not (target / "docs" / "engineering" / "model-routing.md").is_file():
            raise SystemExit("Copier update did not materialize model-routing guidance")
        if args.profile == "multi-agent":
            rendered_agents = (target / "AGENTS.md").read_text(encoding="utf-8")
            rendered_workflow = (target / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
            if "degraded or terminal sibling" not in rendered_agents:
                raise SystemExit("Copier update did not preserve degraded-board admission guidance")
            if "unreadable or un-lockable board" not in rendered_workflow:
                raise SystemExit("Copier update did not preserve fail-closed board guidance")
        openspec_workflow = (target / "docs" / "engineering" / "openspec-workflow.md").read_text(encoding="utf-8")
        if "## Author the outcome contract" not in openspec_workflow:
            raise SystemExit("Copier update did not propagate outcome-oriented OpenSpec guidance")
        updated_config = platform_config.read_text(encoding="utf-8")
        if (
            "[development_backlog]" not in updated_config
            or 'project_label = "project:upgrade-' not in updated_config
            or 'project_owner = "lehard"' not in updated_config
            or "project_number = 1" not in updated_config
        ):
            raise SystemExit("Copier update did not migrate Development Backlog authoring configuration")
        if list(target.rglob("*.rej")):
            raise SystemExit("Copier update left .rej files")

        run(["python3", "-m", "compileall", "-q", "scripts"], target)
        doctor = subprocess.run(["python3", "scripts/platform_doctor.py"], cwd=target, text=True)
        if doctor.returncode != 0:
            raise SystemExit(doctor.returncode)

        if args.profile == "standard":
            # Consumer canary for dev-platform#300: a standard-profile
            # checkout has no linked worktree, so routing preflight must
            # still be able to record a parent-only route against a real
            # rendered project (not only the central template module).
            change = target / "openspec" / "changes" / "upgrade-smoke-routing-canary"
            change.mkdir(parents=True)
            (change / ".managed-task.json").write_text(
                json.dumps({"source_issue": "lehard/development-backlog#0", "change": "upgrade-smoke-routing-canary"}),
                encoding="utf-8",
            )
            probe = subprocess.run(
                [
                    "python3", "scripts/model_routing.py", "prepare",
                    "--provider", "codex", "--profile", "standard",
                    "--rationale", "upgrade smoke: prove standard-profile routing preflight composes",
                ],
                cwd=target, text=True, capture_output=True,
            )
            if probe.returncode != 0:
                raise SystemExit(f"standard-profile routing preflight canary failed: {probe.stderr or probe.stdout}")
            recorded = json.loads(probe.stdout)
            if recorded.get("topology") != "standalone-clone":
                raise SystemExit(
                    "standard-profile routing preflight did not record a standalone-clone parent-only route: "
                    f"{recorded.get('topology')!r}"
                )
            print("Standard-profile routing preflight canary passed: parent-only standalone-clone route recorded.")

        status = run(["git", "status", "--porcelain"], target, capture=True).stdout
        visible_artifacts = [relative for relative in cuby_like_artifacts if relative in status]
        if visible_artifacts:
            raise SystemExit(
                "Copier update made Cuby-like synthetic artifacts visible to Git: "
                + ", ".join(visible_artifacts)
            )
        print(f"Upgrade smoke passed: base={base_ref} profile={args.profile} publish={args.publish_mode}")
        if status.strip():
            print("Expected post-update diff is present and reviewable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
