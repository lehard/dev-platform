#!/usr/bin/env python3
"""Render smoke for `template/AGENTS.md.jinja` across representative profiles.

This is the `instruction-behavior-change`/`docs-semantic` supporting check
described in this change's design: a template edit that is otherwise pure
prose must still fail if it breaks rendering or drops a required section for
any supported profile, without needing the full Copier factory-render CI step
or the Python unit suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

import jinja2

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "template" / "AGENTS.md.jinja"

# One representative combination per supported workflow_profile, mirroring the
# profiles exercised by the "Render factory profiles" CI step.
PROFILES = [
    {
        "workflow_profile": "light",
        "harness_mode": "platform",
        "protected_main": False,
        "publish_mode": "direct",
        "pr_merge_mode": "auto",
        "main_branch": "main",
    },
    {
        "workflow_profile": "standard",
        "harness_mode": "platform",
        "protected_main": True,
        "publish_mode": "pr",
        "pr_merge_mode": "auto",
        "main_branch": "main",
    },
    {
        "workflow_profile": "multi-agent",
        "harness_mode": "platform",
        "protected_main": True,
        "publish_mode": "pr",
        "pr_merge_mode": "auto",
        "main_branch": "main",
    },
]

REQUIRED_HEADINGS = [
    "## Sources of truth",
    "## Task intents",
    "## Always-on invariants",
    "## Profile",
    "## Entrypoints",
    "## Where the detailed contract lives",
    "## Ownership",
]


def render(context: dict[str, object]) -> str:
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    template = env.from_string(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.render(**context)


def main() -> int:
    if not TEMPLATE_PATH.is_file():
        print(f"Template not found: {TEMPLATE_PATH}")
        return 1

    problems: list[str] = []
    for profile in PROFILES:
        label = profile["workflow_profile"]
        try:
            rendered = render(profile)
        except jinja2.exceptions.TemplateError as exc:
            problems.append(f"profile={label}: render failed: {exc}")
            continue
        if not rendered.strip():
            problems.append(f"profile={label}: render produced empty output")
            continue
        missing = [heading for heading in REQUIRED_HEADINGS if heading not in rendered]
        if missing:
            problems.append(f"profile={label}: missing required section(s): {', '.join(missing)}")

    if problems:
        print(f"{len(problems)} template render problem(s) found:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Template render smoke: {len(PROFILES)} profile(s) OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
