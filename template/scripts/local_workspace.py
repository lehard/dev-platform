#!/usr/bin/env python3
"""Opt-in operator-local source permissions; standalone for older projects.

No credentials, machine paths or user identities are part of this runtime.
Policies and attachment receipts live in the reviewed external runtime directory.
"""
from __future__ import annotations

import argparse
import errno
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

POLICY_KEY = 'devPlatform.localWorkspacePolicy'
VERSION = 1
EXCLUDED = {'.git', '.claude', '.codex', '.aws', '.ssh', '.gnupg',
            'node_modules', 'vendor', '.venv', 'venv', '__pycache__', '.cache',
            'dist', 'build', 'coverage', '.next', '.turbo', '.DS_Store',
            '.npm', '.yarn', '.pnpm-store', '.pytest_cache', '.mypy_cache'}
SECRET_PATTERNS = ('.npmrc', '.netrc', '.pypirc', '.env*', '*.pem', '*.key', '*credentials*', '*secret*', '*.p12', '*.pfx')
HOOKS = ('applypatch-msg', 'pre-applypatch', 'post-applypatch', 'pre-commit',
         'pre-merge-commit', 'prepare-commit-msg', 'commit-msg', 'post-commit',
         'pre-rebase', 'post-checkout', 'post-merge', 'pre-push', 'pre-auto-gc',
         'post-rewrite', 'sendemail-validate', 'fsmonitor-watchman', 'post-index-change', 'reference-transaction',
         'push-to-checkout', 'pre-receive', 'update', 'post-receive', 'post-update', 'proc-receive')


class PolicyError(RuntimeError):
    pass


def git(root: Path, *args: str, optional: bool = False) -> str | None:
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    result = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root), *args], env=env,
                            text=True, capture_output=True)
    if result.returncode:
        if optional and result.returncode == 1:
            return None
        raise PolicyError(result.stderr.strip() or 'Git lookup failed')
    return result.stdout.strip()


def absolute(path: str | Path) -> Path:
    """Reject symlinks in every existing component, including parent directories."""
    path = Path(os.path.abspath(path))
    if path in (Path('/'), Path.home()):
        raise PolicyError(f'refusing broad path: {path}')
    for component in [*reversed(path.parents), path]:
        if component.is_symlink():
            raise PolicyError(f'refusing symlink: {component}')
    return path


def shared_directory(path: Path) -> None:
    path = absolute(path)
    if not path.exists():
        if not path.parent.exists():
            shared_directory(path.parent)
        path.mkdir(mode=0o2770)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise PolicyError(f'expected shared directory: {path}')
    groups = set(os.getgroups()) | {os.getegid()}
    if info.st_gid not in groups:
        if info.st_uid != os.geteuid():
            raise PolicyError(f'owner must enroll generated directory in a shared group: {path}')
        os.chown(path, -1, os.getegid())
        info = path.stat()
    bits = 0o2070
    if info.st_mode & bits != bits:
        if info.st_uid != os.geteuid():
            raise PolicyError(f'owner must enable group inheritance: {path}')
        path.chmod(stat.S_IMODE(info.st_mode) | bits)
        if path.stat().st_mode & bits != bits:
            raise PolicyError(f'filesystem cannot retain shared directory permissions: {path}')


def reviewed_runtime(registry: dict) -> bytes:
    source = registry.get('runtime_source')
    if source is None:
        return Path(__file__).read_bytes()
    root = absolute(source['checkout'])
    if git(root, 'rev-parse', '--show-toplevel') != str(root):
        raise PolicyError('runtime source must be an integration checkout')
    if git(root, 'remote', 'get-url', 'origin') != source['origin']:
        raise PolicyError('runtime source origin mismatch')
    if git(root, 'symbolic-ref', '--short', 'HEAD') != source['branch']:
        raise PolicyError('runtime source is not on its reviewed branch')
    path = relative(source['path'])
    payload = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root),
                              'show', f'HEAD:{path.as_posix()}'], check=True, capture_output=True).stdout
    if absolute(root / path).read_bytes() != payload:
        raise PolicyError('runtime source has uncommitted changes')
    return payload


def read_json(path: Path) -> dict:
    path = absolute(path)
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('version') != VERSION:
        raise PolicyError(f'unsupported policy/registry version: {path}')
    return data


def write(path: Path, payload: bytes, mode: int = 0o660) -> None:
    path = absolute(path)
    if mode == 0o600:
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        shared_directory(path.parent)
    if path.exists() and path.read_bytes() == payload and stat.S_IMODE(path.stat().st_mode) == mode:
        return
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise PolicyError(f'unsafe generated file: {path}')
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
            os.fchmod(handle.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, data: dict) -> None:
    write(path, (json.dumps(data, indent=2, sort_keys=True) + '\n').encode())


def relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise PolicyError(f'expected bounded relative source root: {value!r}')
    return path


def excluded(path: Path, extra: list[str]) -> bool:
    return (('.agents' in path.parts and path.parts[:2] != ('.agents', 'skills')) or any(part in EXCLUDED or any(fnmatch.fnmatch(part.lower(), pattern) for pattern in SECRET_PATTERNS)
               for part in path.parts) or any(fnmatch.fnmatch(path.as_posix(), pattern) for pattern in extra))


def checkout(root: Path, policy: dict, *, integration_only: bool = False) -> Path:
    root = absolute(root)
    top = Path(git(root, 'rev-parse', '--show-toplevel'))
    if top != root:
        raise PolicyError(f'command requires checkout root: {top}')
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    integration = absolute(policy['checkout'])
    workspaces = [absolute(value) for value in policy['workspace_roots']]
    if not any(root == workspace or workspace in root.parents for workspace in workspaces):
        raise PolicyError(f'checkout is outside reviewed workspace roots: {root}')
    if common != integration / '.git' or git(root, 'remote', 'get-url', 'origin') != policy['origin']:
        raise PolicyError(f'repository identity mismatch: {root}')
    if integration_only and root != integration:
        raise PolicyError(f'attachment requires integration checkout: {root}')
    if root != integration:
        marker = root / '.git'
        admin = Path(git(root, 'rev-parse', '--absolute-git-dir'))
        for item in (root, marker, admin):
            if absolute(item).stat().st_uid != os.geteuid():
                raise PolicyError(f'foreign active worktree; owner must act: {item}')
    return root


def group_id(value: str | int) -> int:
    if os.name != 'posix':
        raise PolicyError('local workspace permissions require POSIX groups')
    import grp
    try:
        gid = grp.getgrgid(int(value)).gr_gid if str(value).isdecimal() else grp.getgrnam(str(value)).gr_gid
    except KeyError as exc:
        raise PolicyError(f'unknown shared group: {value}') from exc
    if gid not in set(os.getgroups()) | {os.getegid()}:
        raise PolicyError(f'current user is not a member of group {value}; re-login after group enrollment')
    return gid


def _open(path: Path) -> int:
    """Open through no-follow directory descriptors, avoiding parent-link races."""
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        parts = path.parts[1:]
        for i, name in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if i < len(parts) - 1:
                flags |= os.O_DIRECTORY
            try:
                new = os.open(name, flags, dir_fd=fd)
            except PermissionError:
                if i < len(parts) - 1:
                    raise
                # Owner-created write-only sources still yield a stable descriptor for fchmod/fchown.
                try:
                    new = os.open(name, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                except OSError:
                    raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), name) from None
            os.close(fd)
            fd = new
        return fd
    except BaseException:
        os.close(fd)
        raise


def expected_bits(info: os.stat_result) -> int:
    return 0o2070 if stat.S_ISDIR(info.st_mode) else 0o060


def _unreadable(path: Path, gid: int) -> list[str]:
    """Diagnose, never mutate, an entry that cannot be opened, via the no-follow parent descriptor."""
    pfd = None
    try:
        pfd = _open(path.parent)
        info = os.stat(path.name, dir_fd=pfd, follow_symlinks=False)
        if not (stat.S_ISDIR(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1)):
            return []
        bits = expected_bits(info)
        if info.st_gid == gid and info.st_mode & bits == bits:
            return []
        return [f'{path}: owner uid={info.st_uid}, gid={info.st_gid}, mode={stat.S_IMODE(info.st_mode):04o}; '
                f'owner must run chgrp {gid} {shlex.quote(str(path))} && chmod '
                f'{"g+rwxs" if stat.S_ISDIR(info.st_mode) else "g+rw"} {shlex.quote(str(path))}']
    except FileNotFoundError:
        return []
    except (OSError, NotImplementedError) as exc:
        return [f'{path}: cannot inspect/repair: {exc}']
    finally:
        if pfd is not None:
            os.close(pfd)


def audit(root: Path, policy: dict, *, repair: bool = False) -> list[str]:
    root = checkout(root, policy)
    gid = group_id(policy['group'])
    extra = policy.get('exclude', [])
    allowed = [relative(value) for value in policy['source_roots']]
    if not allowed:
        raise PolicyError('source_roots must be explicitly reviewed and non-empty')
    # The explicit source allowlist bounds tracked and untracked paths alike.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    tracked = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root), 'ls-files', '-z'], env=env,
                             capture_output=True, check=True).stdout
    candidates = {root}
    findings = []
    def traversal_error(exc):
        findings.append(f'{exc.filename}: cannot enumerate approved source/admin directory: {exc}')
    for name in tracked.decode('utf-8', 'surrogateescape').split('\0'):
        if name and any(Path(name) == base or base in Path(name).parents for base in allowed) and not excluded(Path(name), extra):
            candidates.add(root / relative(name))
    for local in allowed:
        if excluded(local, extra):
            raise PolicyError(f'source root is excluded: {local}')
        base = root / local
        for boundary in (base, *(parent for parent in base.parents if parent != root and root in parent.parents)):
            if os.path.lexists(boundary / '.git'):
                raise PolicyError(f'source root crosses into a nested checkout; review source_roots: {boundary}')
        try:
            absolute(base)
        except PolicyError:
            continue
        if base.exists():
            candidates.add(base)
            for current, directories, files in os.walk(base, followlinks=False, onerror=traversal_error):
                parent = Path(current)
                # Nested checkouts (own .git entry) are other repositories or foreign worktrees; never descend.
                directories[:] = [name for name in directories if not excluded((parent / name).relative_to(root), extra)
                                  and not (parent / name).is_symlink() and not os.path.lexists(parent / name / '.git')]
                candidates.update(parent / name for name in [*directories, *files]
                                  if not excluded((parent / name).relative_to(root), extra))
    for path in list(candidates):
        candidates.update(parent for parent in path.parents if parent != root and root in parent.parents)
    # Only this user's worktree administration, never the common Git tree.
    if root != Path(policy['checkout']):
        admin = absolute(Path(git(root, 'rev-parse', '--absolute-git-dir')))
        candidates.add(admin)
        candidates.add(root / '.git')
        for current, directories, files in os.walk(admin, followlinks=False, onerror=traversal_error):
            directories[:] = [name for name in directories if not (Path(current) / name).is_symlink()]
            candidates.update(Path(current) / name for name in [*directories, *files])
    def nested(path: Path) -> bool:
        return any(os.path.lexists(item / '.git') for item in (path, *path.parents) if item != root and root in item.parents)

    for path in sorted(candidates):
        if nested(path):
            continue
        fd = None
        try:
            fd = _open(path)
            info = os.fstat(fd)
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                continue
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                findings.append(f'{path}: refusing hardlinked source')
                continue
            bits = expected_bits(info)
            if info.st_gid == gid and info.st_mode & bits == bits:
                continue
            if repair and info.st_uid == os.geteuid():
                current = path.lstat()
                if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
                    findings.append(f'{path}: replaced before repair; rerun owner audit')
                    continue
                if info.st_gid != gid:
                    os.fchown(fd, -1, gid)
                os.fchmod(fd, stat.S_IMODE(os.fstat(fd).st_mode) | bits)
                updated = os.fstat(fd)
                current = path.lstat()
                if (updated.st_dev, updated.st_ino) != (current.st_dev, current.st_ino):
                    findings.append(f'{path}: replaced during repair; rerun owner audit')
                    continue
                if updated.st_gid == gid and updated.st_mode & bits == bits:
                    continue
            findings.append(f'{path}: owner uid={info.st_uid}, gid={info.st_gid}, mode={stat.S_IMODE(info.st_mode):04o}; '
                            f'owner must run chgrp {gid} {shlex.quote(str(path))} && chmod '
                            f'{"g+rwxs" if stat.S_ISDIR(info.st_mode) else "g+rw"} {shlex.quote(str(path))}')
        except FileNotFoundError:
            continue
        except OSError as exc:
            # Symlinks are deliberately skipped, including parent escapes.
            if exc.errno == errno.EACCES:
                findings.extend(_unreadable(path, gid))
                continue
            if exc.errno not in (errno.ELOOP, errno.ENOTDIR):
                findings.append(f'{path}: cannot inspect/repair: {exc}')
        finally:
            if fd is not None:
                os.close(fd)
    return findings


def policy_for(root: Path) -> Path | None:
    # Staged/non-Git fixtures have no opt-in contract yet.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    probe = subprocess.run(['git', '-C', str(root), 'rev-parse', '--git-dir'], capture_output=True, env=env)
    if probe.returncode:
        return None
    value = git(root, 'config', '--local', '--get', POLICY_KEY, optional=True)
    return absolute(value) if value else None


def admit(root: Path) -> None:
    policy = policy_for(root)
    if policy:
        findings = audit(root, read_json(policy))
        if findings:
            raise PolicyError('local source admission blocked:\n' + '\n'.join(findings))


def attach(root: Path, policy_path: Path, runtime: Path) -> None:
    policy = read_json(policy_path)
    checkout(root, policy, integration_only=True)
    state_path = policy_path.with_suffix('.attachment.json')
    dispatcher = policy_path.with_suffix('.hooks')
    configured = git(root, 'config', '--local', '--get', 'core.hooksPath', optional=True)
    if state_path.exists():
        state = read_json(state_path)
        if configured not in (str(dispatcher), state['original_config']) or state['checkout'] != str(root):
            raise PolicyError(f'attachment config changed; operator review required: {root}')
    else:
        if policy_for(root) is not None:
            raise PolicyError(f'policy already configured; operator review required: {root}')
        original_dir = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks'))
        state = {'version': VERSION, 'checkout': str(root), 'original_config': configured,
                 'original_directory': str(original_dir), 'effective_config': git(root, 'config', '--get', 'core.hooksPath', optional=True), 'dispatcher': str(dispatcher),
                 'runtime': str(runtime), 'python': 'python3'}
        write_json(state_path, state)
    dispatcher = absolute(dispatcher)
    shared_directory(dispatcher)
    for hook in HOOKS:
        # Inherit stdin directly through the dispatcher; audit never consumes it.
        command = [state['python'], str(runtime), 'hook', '--policy', str(policy_path), '--name', hook]
        payload = ('#!/bin/sh\nexec ' + shlex.join(command) + ' -- "$@"\n').encode()
        target = dispatcher / hook
        if target.exists() and target.read_bytes() != payload:
            raise PolicyError(f'generated hook changed; refusing update: {target}')
        write(target, payload, 0o770)
    if policy_for(root) != policy_path:
        git(root, 'config', '--local', POLICY_KEY, str(policy_path))
    if configured != str(dispatcher):
        git(root, 'config', '--local', 'core.hooksPath', str(dispatcher))


def detach(root: Path) -> None:
    policy_path = policy_for(root)
    if policy_path is None:
        return
    checkout(root, read_json(policy_path), integration_only=True)
    state_path = policy_path.with_suffix('.attachment.json')
    state = read_json(state_path)
    if git(root, 'config', '--local', '--get', 'core.hooksPath', optional=True) != state['dispatcher']:
        raise PolicyError('hooks configuration changed; refusing removal')
    dispatcher = absolute(state['dispatcher'])
    for hook in HOOKS:
        command = [state['python'], state['runtime'], 'hook', '--policy', str(policy_path), '--name', hook]
        expected = ('#!/bin/sh\nexec ' + shlex.join(command) + ' -- "$@"\n').encode()
        path = absolute(dispatcher / hook)
        if path.exists() and path.read_bytes() != expected:
            raise PolicyError(f'generated hook changed; refusing removal: {path}')
    if state['original_config'] is None:
        git(root, 'config', '--local', '--unset', 'core.hooksPath')
    else:
        git(root, 'config', '--local', 'core.hooksPath', state['original_config'])
    git(root, 'config', '--local', '--unset', POLICY_KEY)
    for hook in HOOKS:
        (dispatcher / hook).unlink(missing_ok=True)
    if not any(dispatcher.iterdir()):
        dispatcher.rmdir()
    state_path.unlink()


def external_path(path: Path) -> Path:
    path = absolute(path)
    for ancestor in (path, *path.parents):
        if (ancestor / '.git').exists() or (ancestor / '.git').is_symlink():
            raise PolicyError(f'runtime/registry must be outside all project checkouts: {path}')
    return path


def sync(registry_path: Path) -> list[str]:
    if os.name != 'posix':
        raise PolicyError('local workspace sync requires POSIX permissions')
    import fcntl

    os.umask(0o002)
    external_path(registry_path)
    runtime_dir = external_path(read_json(registry_path)['runtime_dir'])
    shared_directory(runtime_dir)
    fd = os.open(runtime_dir / '.sync.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o660)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PolicyError('unsafe sync lock')
        if info.st_uid == os.geteuid():
            os.fchmod(fd, stat.S_IMODE(info.st_mode) | 0o060)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PolicyError('another fleet sync is active; retry after it completes') from exc
        return _sync(registry_path)
    finally:
        os.close(fd)


def _sync(registry_path: Path) -> list[str]:
    registry = read_json(registry_path)
    runtime_dir = absolute(registry['runtime_dir'])
    runtime = runtime_dir / 'local_workspace.py'
    write(runtime, reviewed_runtime(registry), 0o770)
    digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
    write_json(runtime_dir / 'runtime.json', {'version': VERSION, 'sha256': digest})
    projects = registry['projects']
    origins = [item['origin'] for item in projects]
    if len(set(origins)) != len(origins):
        raise PolicyError('duplicate registry origins')
    found = set()
    findings = []
    for workspace in registry['workspace_roots']:
        workspace = absolute(workspace)
        if not workspace.is_dir():
            findings.append(f'unavailable workspace: {workspace}')
            continue
        for root in sorted(workspace.iterdir()):
            if root.is_symlink() or not root.is_dir() or not (root / '.git').is_dir() or (root / '.git').is_symlink():
                continue
            try:
                origin = git(root, 'remote', 'get-url', 'origin')
                matches = [item for item in projects if item['origin'] == origin]
                if not matches:
                    continue
                project = matches[0]
                if project.get('checkout_names') and root.name not in project['checkout_names']:
                    continue
                found.add(origin)
                group_id(project['group'])
                key = hashlib.sha256(str(root).encode()).hexdigest()[:24]
                policy_path = runtime_dir / 'policies' / (key + '.json')
                policy = {'version': VERSION, 'checkout': str(root), 'origin': origin, 'group': project['group'],
                          'source_roots': project['source_roots'], 'exclude': project.get('exclude', []),
                          'workspace_roots': registry['workspace_roots']}
                # Validate roots before attaching; malformed registries must not widen scope.
                for value in policy['source_roots']:
                    if excluded(relative(value), policy['exclude']):
                        raise PolicyError(f'excluded source root: {value}')
                if not policy['source_roots']:
                    raise PolicyError('empty source_roots')
                write_json(policy_path, policy)
                source_findings = audit(root, policy, repair=True)
                findings.extend(source_findings)
                if source_findings and policy_for(root) is None:
                    findings.append(f'{root}: attachment pending owner repair')
                    continue
                attach(root, policy_path, runtime)
                worktrees = git(root, 'worktree', 'list', '--porcelain', '-z')
                for field in worktrees.split('\0'):
                    if not field.startswith('worktree '):
                        continue
                    task = Path(field[len('worktree '):])
                    if task == root or workspace not in task.parents:
                        continue
                    try:
                        checkout(task, policy)
                    except PolicyError as exc:
                        if 'foreign active worktree' in str(exc):
                            continue
                        raise
                    findings.extend(audit(task, policy, repair=True))
            except (PolicyError, OSError, subprocess.CalledProcessError) as exc:
                findings.append(f'{root}: {exc}')
    findings.extend(f'unavailable registered origin: {origin}' for origin in origins if origin not in found)
    return findings


def launchagent(registry: Path, destination: Path, *, remove: bool = False) -> None:
    if sys.platform != 'darwin':
        raise PolicyError('LaunchAgent installation requires macOS')
    if destination != Path.home() / 'Library/LaunchAgents/dev.platform.local-workspace.plist':
        raise PolicyError('LaunchAgent destination must be the current user Library/LaunchAgents')
    if remove:
        label = f'gui/{os.geteuid()}/dev.platform.local-workspace'
        if subprocess.run(['launchctl', 'print', label], capture_output=True).returncode == 0:
            result = subprocess.run(['launchctl', 'bootout', f'gui/{os.geteuid()}', str(destination)], capture_output=True)
            if result.returncode:
                raise PolicyError('LaunchAgent unload failed; keep plist and resolve launchctl error before detaching')
        if destination.exists():
            if absolute(destination).stat().st_uid != os.geteuid():
                raise PolicyError('foreign LaunchAgent owner')
            destination.unlink()
        return
    config = read_json(registry)
    runtime = absolute(config['runtime_dir']) / 'local_workspace.py'
    if not runtime.is_file():
        raise PolicyError('run sync to install the reviewed runtime first')
    content = plistlib.dumps({'Label': 'dev.platform.local-workspace',
                             'ProgramArguments': [sys.executable, str(runtime), 'sync', '--registry', str(registry)],
                             'RunAtLoad': True, 'StartInterval': 300, 'Umask': 2,
                             'StandardOutPath': str(runtime.parent / f'sync-{os.geteuid()}.log'),
                             'StandardErrorPath': str(runtime.parent / f'sync-{os.geteuid()}.log')})
    if not destination.exists() or destination.read_bytes() != content:
        label = f'gui/{os.geteuid()}/dev.platform.local-workspace'
        if subprocess.run(['launchctl', 'print', label], capture_output=True).returncode == 0:
            result = subprocess.run(['launchctl', 'bootout', f'gui/{os.geteuid()}', str(destination)], capture_output=True)
            if result.returncode:
                raise PolicyError('LaunchAgent unload failed; refusing replacement')
        write(destination, content, 0o600)
        subprocess.run(['launchctl', 'bootstrap', f'gui/{os.geteuid()}', str(destination)], check=True)
    else:
        # Retry a previously written but un-loaded agent without changing the plist.
        label = f'gui/{os.geteuid()}/dev.platform.local-workspace'
        if subprocess.run(['launchctl', 'print', label], capture_output=True).returncode:
            subprocess.run(['launchctl', 'bootstrap', f'gui/{os.geteuid()}', str(destination)], check=True)


def inherited_hooks_path(root: Path) -> str | None:
    result = subprocess.run(['git', '-C', str(root), 'config', '--show-scope', '--get-all', 'core.hooksPath'],
                            capture_output=True, text=True)
    values = [line.split('\t', 1)[1] for line in result.stdout.splitlines()
              if '\t' in line and line.split('\t', 1)[0] not in ('local', 'worktree')]
    return values[-1] if values else None


def delegate_hooks(root: Path, state: dict, name: str, args: list[str]) -> int:
    original = Path(state['original_directory']) / name
    # A repository-local hooksPath is shared; an inherited one belongs to the invoking user.
    configured_original = state['original_config'] if state['original_config'] is not None else inherited_hooks_path(root)
    if configured_original is None:
        original = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')) / 'hooks' / name
    else:
        expanded = Path(os.path.expanduser(configured_original))
        original = (expanded if expanded.is_absolute() else Path.cwd() / expanded) / name
    hooks = [original] if original.is_file() and os.access(original, os.X_OK) else []
    if name in ('pre-commit', 'pre-merge-commit'):
        doctor = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')) / 'hooks' / name
        if doctor != original and doctor.is_file() and os.access(doctor, os.X_OK) and b'Managed by dev-platform' in doctor.read_bytes():
            hooks.append(doctor)

    def invoke(stdin=None):
        for hook in hooks:
            if stdin is not None:
                stdin.seek(0)
            result = subprocess.run([str(hook), *args], stdin=stdin)
            if result.returncode:
                return result.returncode if result.returncode > 0 else 128 - result.returncode
        return 0

    if len(hooks) > 1 and not sys.stdin.isatty():
        with tempfile.TemporaryFile() as stream:
            shutil.copyfileobj(sys.stdin.buffer, stream)
            return invoke(stream)
    return invoke()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('sync', 'check', 'repair', 'run', 'hook', 'remove', 'install-agent', 'remove-agent'))
    parser.add_argument('--registry', type=Path)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--name', choices=HOOKS)
    argv = sys.argv[1:]
    separator = argv.index('--') if '--' in argv else len(argv)
    options = parser.parse_args(argv[:separator])
    options.args = argv[separator + 1:]
    try:
        if options.command in ('sync', 'install-agent', 'remove-agent'):
            if not options.registry:
                raise PolicyError('--registry is required')
            registry = absolute(options.registry)
            if options.command == 'sync':
                config = read_json(registry)
                runtime = absolute(config['runtime_dir']) / 'local_workspace.py'
                executing_payload = Path(__file__).read_bytes()
                findings = sync(registry)
                if Path(__file__).resolve() == runtime and runtime.read_bytes() != executing_payload:
                    os.execv(sys.executable, [sys.executable, str(runtime), 'sync', '--registry', str(registry)])
                for finding in findings:
                    print(finding, file=sys.stderr)
                return int(bool(findings))
            launchagent(registry, Path.home() / 'Library/LaunchAgents/dev.platform.local-workspace.plist',
                        remove=options.command == 'remove-agent')
            return 0
        root = absolute(options.root)
        if options.command == 'remove':
            detach(root)
            return 0
        path = options.policy or policy_for(root)
        if path is None:
            raise PolicyError('no local source policy is attached')
        policy = read_json(path)
        if options.command == 'hook':
            if not options.name:
                raise PolicyError('--name is required')
            # Git may invoke push hooks in the Git directory; use its worktree identity.
            integration = absolute(policy['checkout'])
            if root == integration / '.git':
                root = integration
            elif integration / '.git/worktrees' in root.parents and (root / 'gitdir').is_file():
                root = absolute((root / 'gitdir').read_text().strip()).parent
            else:
                root = Path(git(root, 'rev-parse', '--show-toplevel'))
            checkout(root, policy)
            state = read_json(path.with_suffix('.attachment.json'))
            result = delegate_hooks(root, state, options.name, options.args)
            if result:
                return result
            if options.name == 'fsmonitor-watchman':
                return 0  # Preserve the fsmonitor protocol; auditing here would recursively query Git.
            findings = audit(root, policy, repair=True)
            for finding in findings:
                print(finding, file=sys.stderr)
            return int(bool(findings))
        checkout(root, policy)
        if options.command == 'run':
            command = options.args[1:] if options.args[:1] == ['--'] else options.args
            if not command:
                raise PolicyError('run requires a command after --')
            os.umask(0o002)
            findings = audit(root, policy, repair=True)
            if findings:
                raise PolicyError('\n'.join(findings))
            try:
                result = subprocess.run(command, cwd=root)
            finally:
                findings = audit(root, policy, repair=True)
                for finding in findings:
                    print(finding, file=sys.stderr)
            return (result.returncode if result.returncode >= 0 else 128 - result.returncode) or int(bool(findings))
        findings = audit(root, policy, repair=options.command == 'repair')
        for finding in findings:
            print(finding, file=sys.stderr)
        return int(bool(findings))
    except (PolicyError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f'local workspace: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
