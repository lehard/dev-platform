#!/usr/bin/env python3
"""Create, verify, and remove a proven-isolated disposable Git repository."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path


MARKER = ".dev-platform-disposable-repository.json"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class SandboxError(RuntimeError):
    pass


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise SandboxError("sandbox root must be an absolute path")
    if not path.is_dir():
        raise SandboxError(f"sandbox root is not an existing directory: {path}")
    return path.resolve()


def _destination(root: Path, name: str) -> Path:
    if not NAME.fullmatch(name) or name in {".", ".."}:
        raise SandboxError("sandbox name must be one safe path component")
    destination = root / name
    if not _within(destination, root):  # Defensive even after component validation.
        raise SandboxError(f"sandbox destination escapes declared root: {destination}")
    return destination


def _git(cwd: Path, *arguments: str) -> str:
    completed = subprocess.run(["git", *arguments], cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git failure"
        raise SandboxError(f"git {' '.join(arguments)} failed in {cwd}: {detail}")
    return completed.stdout.strip()


def _common_dir(repo: Path) -> Path:
    value = Path(_git(repo, "rev-parse", "--git-common-dir"))
    return (repo / value).resolve() if not value.is_absolute() else value.resolve()


def _walk_contained(path: Path, boundary: Path) -> list[Path]:
    """List entries without following symlinks, rejecting shared file inodes."""
    result: list[Path] = []
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            entry = current.lstat()
        except FileNotFoundError as exc:
            raise SandboxError(f"sandbox path disappeared during verification: {current}") from exc
        if not _within(current.absolute(), boundary):
            raise SandboxError(f"traversed path escapes disposable copy: {current}")
        result.append(current)
        if stat.S_ISLNK(entry.st_mode):
            try:
                resolved = current.resolve(strict=True)
            except OSError as exc:
                raise SandboxError(f"cannot resolve sandbox symlink: {current}: {exc}") from exc
            if not _within(resolved, boundary):
                raise SandboxError(f"sandbox symlink escapes disposable copy: {current} -> {resolved}")
            continue
        if stat.S_ISREG(entry.st_mode) and entry.st_nlink > 1:
            raise SandboxError(f"sandbox file has multiple hardlinks: {current}")
        if stat.S_ISDIR(entry.st_mode):
            with os.scandir(current) as children:
                stack.extend(Path(child.path) for child in children)
    return result


def _regular_files(path: Path) -> list[Path]:
    if not path.is_dir():
        raise SandboxError(f"Git object directory is missing: {path}")
    result: list[Path] = []
    for current, directories, filenames in os.walk(path, followlinks=False):
        directories[:] = [name for name in directories if not (Path(current) / name).is_symlink()]
        for name in filenames:
            candidate = Path(current) / name
            if candidate.is_file() and not candidate.is_symlink():
                result.append(candidate)
    return result


def _verify(root: Path, name: str) -> Path:
    destination = _destination(root, name)
    if destination.is_symlink() or not destination.is_dir():
        raise SandboxError(f"sandbox destination is not a real directory: {destination}")
    destination = destination.resolve()
    if not _within(destination, root):
        raise SandboxError(f"sandbox destination escapes declared root: {destination}")
    marker = destination / MARKER
    if marker.is_symlink() or not marker.is_file():
        raise SandboxError(f"sandbox ownership marker is missing or unsafe: {marker}")
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxError(f"sandbox ownership marker is unreadable: {marker}: {exc}") from exc
    if payload.get("version") != 1 or payload.get("root") != str(root) or payload.get("destination") != str(destination):
        raise SandboxError(f"sandbox ownership marker does not match requested root/destination: {marker}")
    source = Path(str(payload.get("source", "")))
    if not source.is_absolute() or not source.is_dir():
        raise SandboxError("sandbox ownership marker has no usable source repository")
    source = source.resolve()
    if _within(source, root):
        raise SandboxError(f"source repository is inside declared sandbox root: {source}")
    _walk_contained(destination, destination)
    git_dir = destination / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir():
        raise SandboxError("sandbox uses .git indirection instead of standalone metadata")
    if (git_dir / "commondir").exists():
        raise SandboxError(f"sandbox Git common-directory metadata is forbidden: {git_dir / 'commondir'}")
    alternates = git_dir / "objects" / "info" / "alternates"
    if alternates.exists():
        raise SandboxError(f"sandbox Git object alternates are forbidden: {alternates}")
    common = _common_dir(destination)
    if common != git_dir.resolve():
        raise SandboxError(f"sandbox Git common directory is not its .git directory: {common}")
    source_common = _common_dir(source)
    if _within(source_common, root):
        raise SandboxError(f"source Git common directory is inside declared sandbox root: {source_common}")
    objects = git_dir / "objects"
    source_objects = source_common / "objects"
    sandbox_files = _regular_files(objects)
    source_ids = {(item.stat().st_dev, item.stat().st_ino) for item in _regular_files(source_objects)}
    for item in sandbox_files:
        inode = item.stat()
        if inode.st_nlink > 1:
            raise SandboxError(f"sandbox Git object has multiple hardlinks: {item}")
        if (inode.st_dev, inode.st_ino) in source_ids:
            raise SandboxError(f"sandbox Git object inode overlaps source: {item}")
    return destination


def _remove_owned_tree(destination: Path, root: Path) -> None:
    # The caller established this exact child path before clone. rmtree's
    # fd-based implementation does not follow directory symlinks; the prior
    # no-follow walk makes an external path escape a hard failure.
    _walk_contained(destination, destination)
    shutil.rmtree(destination)


def create(source_value: str, root_value: str, name: str) -> Path:
    root = _root(root_value)
    source = Path(source_value)
    if not source.is_absolute() or not source.is_dir():
        raise SandboxError("source repository must be an existing absolute directory")
    source = source.resolve()
    if _within(source, root):
        raise SandboxError("source repository must be outside the sandbox root")
    _common_dir(source)  # Establish that it is a Git repository before writing.
    destination = _destination(root, name)
    if destination.exists() or destination.is_symlink():
        raise SandboxError(f"sandbox destination already exists: {destination}")
    completed = subprocess.run(["git", "clone", "--local", "--no-hardlinks", str(source), str(destination)], text=True, capture_output=True, check=False)
    if completed.returncode:
        if destination.exists() and destination.is_dir() and not destination.is_symlink():
            _remove_owned_tree(destination, root)
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git clone failure"
        raise SandboxError(f"isolated clone failed: {detail}")
    try:
        marker = {"version": 1, "root": str(root), "destination": str(destination.resolve()), "source": str(source)}
        (destination / MARKER).write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
        return _verify(root, name)
    except Exception:
        if destination.exists() and destination.is_dir() and not destination.is_symlink():
            _remove_owned_tree(destination, root)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create_parser = commands.add_parser("create")
    create_parser.add_argument("source")
    create_parser.add_argument("root")
    create_parser.add_argument("name")
    for command in ("verify", "cleanup"):
        item = commands.add_parser(command)
        item.add_argument("root")
        item.add_argument("name")
    args = parser.parse_args()
    try:
        if args.command == "create":
            print(create(args.source, args.root, args.name))
        else:
            root = _root(args.root)
            destination = _verify(root, args.name)
            if args.command == "cleanup":
                _remove_owned_tree(destination, root)
            print(destination)
    except SandboxError as exc:
        print(f"refusing disposable repository operation: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
