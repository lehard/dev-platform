#!/usr/bin/env python3
"""Manage provider-neutral optional engineering capabilities.

The canonical descriptor lives in ``dev-platform/capabilities/<id>.toml``.
Project selection is deliberately separate and project-owned in
``dev-platform/capabilities.toml``.  Provider skill files are derived only for
selected capabilities and carry a marker so removal cannot touch unrelated
skills (including OpenSpec-generated integrations).

Lifecycle eval statuses delegated to the shared core are ``run``,
``skip-with-reason``, and ``blocked/unavailable``.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _eval_module():
    """Load the sibling provider-neutral eval surface in source and test copies."""
    try:
        import capability_evals
        return capability_evals
    except ModuleNotFoundError:
        source = Path(__file__).with_name("capability_evals.py")
        spec = importlib.util.spec_from_file_location("capability_evals", source)
        if spec is None or spec.loader is None:
            raise CapabilityError("provider-neutral capability eval surface is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MARKER = "dev-platform-capability"
CAPABILITY_KINDS = {"instruction-only", "tool-backed"}
INVOCATIONS = {"auto+explicit", "explicit-only", "agent-only"}
SUPPORTED_MATERIALIZATION = {"provider-skill-markdown"}


class CapabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Capability:
    identifier: str
    name: str
    description: str
    kind: str
    applicability: str
    invocation: str
    visibility: str
    owner: str
    safety_boundary: str
    dependencies: tuple[str, ...]
    materialization: str
    update_policy: str
    removal_policy: str
    tool_adapter: str | None
    provenance: dict[str, str]
    eval: dict[str, str]
    instruction: str


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CapabilityError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CapabilityError(f"{path} must contain a TOML table")
    return value


def _safe_child(root: Path, relative: str, label: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise CapabilityError(f"{label} escapes the repository: {relative!r}") from exc
    return candidate


def _required_string(table: dict[str, Any], key: str, label: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CapabilityError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def load_descriptor(root: Path, path: Path) -> Capability:
    data = _load_toml(path)
    raw = data.get("capability")
    provenance = data.get("provenance")
    eval_data = data.get("eval", {})
    if not isinstance(raw, dict) or not isinstance(provenance, dict) or not isinstance(eval_data, dict):
        raise CapabilityError(f"{path} requires [capability], [provenance], and optional [eval] tables")
    identifier = _required_string(raw, "id", "capability")
    if not ID_RE.fullmatch(identifier) or path.stem != identifier:
        raise CapabilityError(f"{path} must use a safe id matching its filename")
    kind = _required_string(raw, "kind", "capability")
    invocation = _required_string(raw, "invocation", "capability")
    materialization = _required_string(raw, "materialization", "capability")
    if kind not in CAPABILITY_KINDS:
        raise CapabilityError(f"{identifier}: unsupported capability kind {kind!r}")
    if invocation not in INVOCATIONS:
        raise CapabilityError(f"{identifier}: unsupported invocation intent {invocation!r}")
    if materialization not in SUPPORTED_MATERIALIZATION:
        raise CapabilityError(f"{identifier}: unsupported materialization {materialization!r}")
    dependencies = raw.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(isinstance(value, str) and value.strip() for value in dependencies):
        raise CapabilityError(f"{identifier}: capability.dependencies must be a list of strings")
    normalized_provenance = {key: _required_string(provenance, key, "provenance") for key in ("source", "revision", "path", "license", "content_sha256")}
    if not SHA256_RE.fullmatch(normalized_provenance["content_sha256"]):
        raise CapabilityError(f"{identifier}: provenance.content_sha256 must be a lowercase SHA-256")
    instruction_path = _safe_child(root, normalized_provenance["path"], f"{identifier} provenance path")
    if not instruction_path.is_file():
        raise CapabilityError(f"{identifier}: instruction file is missing: {normalized_provenance['path']}")
    instruction = instruction_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(instruction.encode()).hexdigest()
    if digest != normalized_provenance["content_sha256"]:
        raise CapabilityError(f"{identifier}: instruction hash does not match provenance.content_sha256")
    tool_adapter = raw.get("tool_adapter")
    if kind == "tool-backed":
        if not isinstance(tool_adapter, str) or not tool_adapter.strip():
            raise CapabilityError(f"{identifier}: tool-backed capability requires a non-empty tool_adapter")
        adapter_path = _safe_child(root, tool_adapter.strip(), f"{identifier} tool adapter")
        if not adapter_path.is_file():
            raise CapabilityError(f"{identifier}: isolated tool adapter is missing: {tool_adapter}")
        tool_adapter = tool_adapter.strip()
    elif tool_adapter is not None:
        raise CapabilityError(f"{identifier}: instruction-only capability must not declare tool_adapter")
    return Capability(
        identifier=identifier,
        name=_required_string(raw, "name", "capability"),
        description=_required_string(raw, "description", "capability"),
        kind=kind,
        applicability=_required_string(raw, "applicability", "capability"),
        invocation=invocation,
        visibility=_required_string(raw, "visibility", "capability"),
        owner=_required_string(raw, "owner", "capability"),
        safety_boundary=_required_string(raw, "safety_boundary", "capability"),
        dependencies=tuple(dependencies),
        materialization=materialization,
        update_policy=_required_string(raw, "update_policy", "capability"),
        removal_policy=_required_string(raw, "removal_policy", "capability"),
        tool_adapter=tool_adapter,
        provenance=normalized_provenance,
        eval={key: str(value) for key, value in eval_data.items() if isinstance(value, (str, int, float, bool))},
        instruction=instruction,
    )


def load_registry(root: Path) -> dict[str, Capability]:
    directory = root / "dev-platform" / "capabilities"
    if not directory.is_dir():
        raise CapabilityError("capability descriptor directory is missing: dev-platform/capabilities")
    registry: dict[str, Capability] = {}
    for path in sorted(directory.glob("*.toml")):
        capability = load_descriptor(root, path)
        if capability.identifier in registry:
            raise CapabilityError(f"duplicate capability id: {capability.identifier}")
        registry[capability.identifier] = capability
    if not registry:
        raise CapabilityError("capability descriptor directory is empty")
    return registry


def selection_path(root: Path) -> Path:
    return root / "dev-platform" / "capabilities.toml"


def load_selection(root: Path) -> list[str]:
    path = selection_path(root)
    if not path.is_file():
        raise CapabilityError("project capability selection is missing: dev-platform/capabilities.toml")
    data = _load_toml(path)
    if data.get("version") != 1:
        raise CapabilityError("capability selection version must be 1")
    enabled = data.get("enabled")
    if not isinstance(enabled, list) or not all(isinstance(value, str) and ID_RE.fullmatch(value) for value in enabled):
        raise CapabilityError("capability selection enabled must be a list of safe capability ids")
    if len(set(enabled)) != len(enabled):
        raise CapabilityError("capability selection contains duplicate ids")
    return sorted(enabled)


def write_selection(root: Path, enabled: list[str]) -> None:
    path = selection_path(root)
    normalized = sorted(set(enabled))
    if any(not ID_RE.fullmatch(value) for value in normalized):
        raise CapabilityError("cannot write an unsafe capability id")
    path.write_text("# Project-owned optional engineering capability selection.\nversion = 1\nenabled = " + json.dumps(normalized) + "\n", encoding="utf-8")


def configured_providers(root: Path) -> list[str]:
    config = _load_toml(root / ".dev-platform.toml")
    raw = config.get("agent_tools", "claude,codex")
    if not isinstance(raw, str):
        raise CapabilityError("agent_tools must be a comma-separated string")
    return sorted({value.strip() for value in raw.split(",") if value.strip()})


def support_for(capability: Capability, provider: str) -> dict[str, str]:
    if provider not in {"codex", "claude"}:
        return {"status": "unsupported", "reason": "provider has no platform capability adapter"}
    if capability.invocation != "auto+explicit":
        return {"status": "unsupported", "reason": "platform has no documented native control for this invocation intent"}
    return {"status": "supported", "surface": f".{provider}/skills/dev-platform-{capability.identifier}/SKILL.md"}


def marker(capability: Capability) -> str:
    return f"<!-- {MARKER}:id={capability.identifier} sha256={capability.provenance['content_sha256']} -->"


def derived_path(root: Path, provider: str, capability: Capability) -> Path:
    return root / f".{provider}" / "skills" / f"dev-platform-{capability.identifier}" / "SKILL.md"


def rendered_skill(capability: Capability) -> str:
    return "\n".join((marker(capability), "---", f"name: {capability.identifier}", f"description: {capability.description}", "---", "", capability.instruction.rstrip(), ""))


def remove_derived(root: Path, provider: str, capability: Capability) -> bool:
    path = derived_path(root, provider, capability)
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    if f"{MARKER}:id={capability.identifier} " not in content:
        raise CapabilityError(f"refusing to remove unowned provider skill: {path.relative_to(root)}")
    path.unlink()
    try:
        path.parent.rmdir()
        path.parent.parent.rmdir()
    except OSError:
        pass
    return True


def sync(root: Path, registry: dict[str, Capability], enabled: list[str]) -> dict[str, Any]:
    unknown = [identifier for identifier in enabled if identifier not in registry]
    if unknown:
        raise CapabilityError("selected capability is not declared: " + ", ".join(unknown))
    providers = configured_providers(root)
    changes: list[str] = []
    unsupported: list[dict[str, str]] = []
    for capability in registry.values():
        selected = capability.identifier in enabled
        for provider in providers:
            support = support_for(capability, provider)
            if selected and support["status"] != "supported":
                unsupported.append({"capability": capability.identifier, "provider": provider, "reason": support["reason"]})
                continue
            if not selected:
                if remove_derived(root, provider, capability):
                    changes.append(f"removed {provider}:{capability.identifier}")
                continue
            path = derived_path(root, provider, capability)
            expected = rendered_skill(capability)
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(expected, encoding="utf-8")
                changes.append(f"materialized {provider}:{capability.identifier}")
    return {"enabled": enabled, "changes": changes, "unsupported": unsupported}


def audit(root: Path, registry: dict[str, Capability], enabled: list[str]) -> dict[str, Any]:
    providers = configured_providers(root)
    issues: list[str] = []
    unsupported: list[dict[str, str]] = []
    unknown = [identifier for identifier in enabled if identifier not in registry]
    if unknown:
        issues.append("selected capability is not declared: " + ", ".join(unknown))
    for capability in registry.values():
        for dependency in capability.dependencies:
            dependency_path = _safe_child(root, dependency, f"{capability.identifier} dependency")
            if not dependency_path.exists():
                issues.append(f"missing capability dependency: {capability.identifier}:{dependency}")
        for provider in providers:
            path = derived_path(root, provider, capability)
            support = support_for(capability, provider)
            selected = capability.identifier in enabled
            if selected and support["status"] != "supported":
                unsupported.append({"capability": capability.identifier, "provider": provider, "reason": support["reason"]})
                issues.append(f"selected capability has unsupported invocation mapping: {capability.identifier}:{provider}")
            if selected and support["status"] == "supported":
                if not path.is_file() or path.read_text(encoding="utf-8") != rendered_skill(capability):
                    issues.append(f"derived provider surface is stale or missing: {path.relative_to(root)}")
            elif path.exists() and f"{MARKER}:id={capability.identifier} " in path.read_text(encoding="utf-8"):
                issues.append(f"unselected or unsupported capability remains materialized: {path.relative_to(root)}")
    return {"status": "ok" if not issues else "error", "enabled": enabled, "issues": issues, "unsupported": unsupported}


def catalog_entry(capability: Capability, providers: list[str], enabled: list[str]) -> dict[str, Any]:
    return {
        "id": capability.identifier,
        "name": capability.name,
        "description": capability.description,
        "kind": capability.kind,
        "applicability": capability.applicability,
        "invocation": capability.invocation,
        "enabled": capability.identifier in enabled,
        "owner": capability.owner,
        "provenance": capability.provenance,
        "dependencies": list(capability.dependencies),
        "tool_adapter": capability.tool_adapter,
        "safety_boundary": capability.safety_boundary,
        "eval": capability.eval,
        "providers": {provider: support_for(capability, provider) for provider in providers},
    }


def eval_decision(change_kind: str, *, runtime: str = "unavailable", explicit: bool = False) -> dict[str, str]:
    """Delegate lifecycle decisions to #79 without creating a second registry."""
    normalized = "material" if change_kind == "material" else change_kind
    try:
        return _eval_module().decision_for(normalized, runtime=runtime, explicit=explicit)
    except Exception as exc:
        raise CapabilityError(f"capability eval decision is unavailable: {exc}") from exc


def evaluate_existing(capability: Capability, fixture: Path, *, runtime: str, runs: int) -> dict[str, Any]:
    """Execute a direct audit through the shared #79 core, never a provider subprocess."""
    try:
        evals = _eval_module()
        loaded = evals.load_fixture(fixture)
        if loaded["capability"] != capability.identifier:
            raise CapabilityError(
                f"eval fixture targets {loaded['capability']!r}, not requested capability {capability.identifier!r}"
            )
        if loaded["content_sha256"] != capability.provenance["content_sha256"]:
            raise CapabilityError("eval fixture content hash does not match the canonical capability descriptor")
        return evals.run_fixture(loaded, runtime=runtime, runs=runs)
    except CapabilityError:
        raise
    except Exception as exc:
        raise CapabilityError(f"capability eval could not run: {exc}") from exc


def create_from_descriptor(root: Path, source: Path, enable: bool) -> dict[str, Any]:
    config = _load_toml(root / ".dev-platform.toml")
    if config.get("platform_version") != "source":
        raise CapabilityError(
            "new canonical descriptors are authored only in the Dev Platform source through a managed task; "
            "downstream projects may enable, disable, list, audit, and synchronize released capabilities"
        )
    source = source.resolve()
    if not source.is_file() or source.suffix != ".toml":
        raise CapabilityError("--descriptor must name a TOML descriptor file")
    identifier = source.stem
    if not ID_RE.fullmatch(identifier):
        raise CapabilityError("descriptor filename must be a safe capability id")
    instruction = source.with_suffix(".md")
    if not instruction.is_file():
        raise CapabilityError("create expects a sibling Markdown instruction file")
    destination = root / "dev-platform" / "capabilities"
    destination.mkdir(parents=True, exist_ok=True)
    target_descriptor = destination / source.name
    target_instruction = destination / instruction.name
    if target_descriptor.exists() or target_instruction.exists():
        raise CapabilityError(f"capability {identifier!r} already exists; use update after reviewed descriptor changes")
    shutil.copyfile(source, target_descriptor)
    shutil.copyfile(instruction, target_instruction)
    try:
        registry = load_registry(root)
    except Exception:
        target_descriptor.unlink(missing_ok=True)
        target_instruction.unlink(missing_ok=True)
        raise
    enabled = load_selection(root)
    if enable:
        enabled.append(identifier)
        write_selection(root, enabled)
    result = sync(root, registry, load_selection(root))
    result["eval"] = eval_decision("material")
    return result


def emit(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            print(f"{key}: {value}")
    else:
        print(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage optional engineering capabilities from canonical descriptors.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--quiet", action="store_true", help="suppress successful sync detail")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list declared capabilities and provider support")
    show = sub.add_parser("show", help="show one canonical capability descriptor")
    show.add_argument("id")
    sub.add_parser("validate", help="validate descriptors and project selection without writing")
    sub.add_parser("audit", help="validate descriptors, selection, and derived provider parity")
    sub.add_parser("sync", help="materialize selected capabilities and remove owned stale surfaces")
    enable = sub.add_parser("enable", help="enable an existing capability and synchronize derived surfaces")
    enable.add_argument("id")
    disable = sub.add_parser("disable", help="disable a capability and remove only its owned derived surfaces")
    disable.add_argument("id")
    create = sub.add_parser("create", help="add a reviewed local descriptor plus sibling instruction file")
    create.add_argument("--descriptor", required=True)
    create.add_argument("--enable", action="store_true")
    update = sub.add_parser("update", help="synchronize a reviewed descriptor change and emit its eval decision")
    update.add_argument("id")
    update.add_argument("--change-kind", choices=("metadata", "material", "trigger"), default="material")
    update.add_argument("--fixture", help="run the shared eval immediately when its decision is run")
    update.add_argument("--runtime", choices=("unavailable", "fixture", "codex", "claude"), default="unavailable")
    update.add_argument("--runs", type=int, default=3)
    remove = sub.add_parser("remove", help="alias for disable; preserves canonical descriptor for review/history")
    remove.add_argument("id")
    decision = sub.add_parser("eval-decision", help="classify whether a capability authoring change needs live eval")
    decision.add_argument("--change-kind", choices=("new", "metadata", "material", "trigger", "behavior", "tool", "safety"), required=True)
    decision.add_argument("--runtime", choices=("unavailable", "fixture"), default="unavailable")
    decision.add_argument("--explicit", action="store_true")
    evaluate = sub.add_parser("evaluate", help="directly evaluate an existing capability through the shared #79 core")
    evaluate.add_argument("id")
    evaluate.add_argument("--fixture", required=True)
    evaluate.add_argument("--runtime", choices=("fixture", "codex", "claude"), default="fixture")
    evaluate.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    try:
        if args.command == "eval-decision":
            emit(eval_decision(args.change_kind, runtime=args.runtime, explicit=args.explicit), args.json)
            return 0
        if args.command == "create":
            emit(create_from_descriptor(root, Path(args.descriptor), args.enable), args.json)
            return 0
        registry = load_registry(root)
        enabled = load_selection(root)
        if args.command == "list":
            payload = [catalog_entry(item, configured_providers(root), enabled) for item in registry.values()]
        elif args.command == "show":
            if args.id not in registry:
                raise CapabilityError(f"unknown capability: {args.id}")
            payload = catalog_entry(registry[args.id], configured_providers(root), enabled)
        elif args.command == "validate":
            unknown = [identifier for identifier in enabled if identifier not in registry]
            if unknown:
                raise CapabilityError("selected capability is not declared: " + ", ".join(unknown))
            payload = {"status": "ok", "declared": sorted(registry), "enabled": enabled}
        elif args.command == "audit":
            payload = audit(root, registry, enabled)
            if payload["status"] != "ok":
                emit(payload, args.json)
                return 1
        elif args.command in {"enable", "disable", "remove"}:
            if args.id not in registry:
                raise CapabilityError(f"unknown capability: {args.id}")
            next_enabled = [item for item in enabled if item != args.id]
            if args.command == "enable":
                next_enabled.append(args.id)
            write_selection(root, next_enabled)
            payload = sync(root, registry, load_selection(root))
        elif args.command == "update":
            if args.id not in registry:
                raise CapabilityError(f"unknown capability: {args.id}")
            payload = sync(root, registry, enabled)
            payload["eval"] = eval_decision(args.change_kind, runtime=args.runtime)
            if payload["eval"]["decision"] == "run":
                if not args.fixture:
                    raise CapabilityError("a run decision requires --fixture so the bounded #79 eval path can execute")
                payload["eval"]["report"] = evaluate_existing(
                    registry[args.id], Path(args.fixture), runtime=args.runtime, runs=args.runs,
                )
        elif args.command == "evaluate":
            if args.id not in registry:
                raise CapabilityError(f"unknown capability: {args.id}")
            payload = evaluate_existing(registry[args.id], Path(args.fixture), runtime=args.runtime, runs=args.runs)
        elif args.command == "sync":
            payload = sync(root, registry, enabled)
        else:
            raise CapabilityError(f"unsupported command: {args.command}")
        if not args.quiet:
            emit(payload, args.json)
        return 0
    except CapabilityError as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Capability manager blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
