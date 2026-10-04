"""Readable identity only; exact private ownership stays in canonical Issue links."""
from __future__ import annotations

import re
from contextlib import contextmanager
import hashlib
import tempfile
import os
import stat
from pathlib import Path
try:
    import fcntl
except ImportError:  # read-only identity operations remain portable
    fcntl = None

TOKEN = re.compile(r"BR-[1-9][0-9]*(?:/T[1-9][0-9]*)?")
RESERVATION = re.compile(r"<!-- br-child:(\S+/\S+#[1-9][0-9]*):([1-9][0-9]*) -->")


class IdentityError(RuntimeError):
    pass


def validate(value: object, *, child: bool | None = None) -> str:
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise IdentityError("invalid safe BR identity")
    if child is not None and ("/T" in value) != child:
        raise IdentityError("wrong BR identity kind")
    return value


def parent_identity(reference: str) -> str:
    match = re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#([1-9][0-9]*)", reference)
    if not match:
        raise IdentityError("invalid canonical Requirement reference")
    return f"BR-{match[1]}"


def identity_in(body: str) -> str | None:
    values = re.findall(r"^Work identity: (.*)$", body.replace("\r\n", "\n"), re.MULTILINE)
    if len(values) > 1:
        raise IdentityError("duplicate Work identity fields")
    return validate(values[0]) if values else None


def with_identity(body: str, value: str) -> str:
    validate(value)
    old = identity_in(body)
    if old and old != value:
        raise IdentityError(f"conflicting work identity: expected {value}, found {old}")
    return body if old else body + f"\n\nWork identity: {value}\n"


def assignments(parent_body: str, requirement: str, children: dict[str, str]) -> dict[str, int]:
    parent = parent_identity(requirement)
    if identity_in(parent_body) not in (None, parent):
        raise IdentityError("parent work identity disagrees with canonical Requirement")
    result: dict[str, int] = {}

    def add(ref: str, ordinal: int) -> None:
        if ref in result and result[ref] != ordinal:
            raise IdentityError(f"conflicting ordinal reservation for {ref}")
        if ordinal in result.values() and result.get(ref) != ordinal:
            raise IdentityError(f"duplicate child ordinal T{ordinal}; repair conflicting Issue records")
        result[ref] = ordinal

    for ref, ordinal in RESERVATION.findall(parent_body):
        add(ref, int(ordinal))
    if parent_body.count("<!-- br-child:") != len(RESERVATION.findall(parent_body)):
        raise IdentityError("malformed child ordinal reservation")
    for ref, body in children.items():
        parents = re.findall(r"^Requirement: (\S+)\s*$", body, re.MULTILINE)
        value = identity_in(body)
        if parents and parents != [requirement]:
            raise IdentityError(f"conflicting canonical parent for {ref}")
        if value:
            validate(value, child=True)
            if not value.startswith(parent + "/T"):
                raise IdentityError(f"child {ref} disagrees with canonical parent identity")
            add(ref, int(value.split("/T")[1]))
    return result


@contextmanager
def allocation_lock(requirement: str):
    # Advisory serialization only; no identity registry and no integration writes.
    if fcntl is None:
        raise IdentityError("child allocation requires host advisory locking support")
    key = hashlib.sha256(requirement.lower().encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / f"dev-platform-br-{key}.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        raise IdentityError(f"cannot open safe allocation lock: {exc}") from exc
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
        os.close(descriptor)
        raise IdentityError("unsafe allocation lock; expected an owner-held regular single-link file")
    with os.fdopen(descriptor, "r+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def task_branch(change: str, identity: str | None = None) -> str:
    """Change owns the path; validated presentation only decorates a new ref."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", change) or '..' in change or change.endswith(('.', '.lock')):
        raise IdentityError("invalid managed branch change")
    prefix = validate(identity, child=True).lower().replace('/t', '-t') + '-' if identity else ''
    return f"agent/{prefix}{change}"


def canonical_child_identity(root: Path, source: str, *, provenance: dict | None = None,
                             requirement: str | None = None) -> str | None:
    """Prove readable identity from reciprocal canonical claims, never prose."""
    import managed_task
    import requirement_intake
    issue = managed_task.fetch_issue(root, *managed_task.issue_ref(source))
    body = str(issue.get('body') or '')
    parents = re.findall(r'^Requirement: (\S+)\s*$', body, re.MULTILINE)
    value = identity_in(body)
    recorded = (provenance or {}).get('work_identity')
    if not parents:
        if value is not None or recorded is not None or requirement is not None:
            raise IdentityError('work identity lacks canonical parent')
        return None
    if len(parents) != 1 or (requirement is not None and parents != [requirement]):
        raise IdentityError('ambiguous or conflicting canonical parent')
    parent = parents[0]
    parent_identity(parent)
    parent_issue = managed_task.fetch_issue(root, *managed_task.issue_ref(parent))
    parent_body = str(parent_issue.get('body') or '')
    if (requirement_intake.CHILD_LABEL not in managed_task.issue_labels(issue)
            or requirement_intake.REQUIREMENT_LABEL not in managed_task.issue_labels(parent_issue)
            or source not in requirement_intake.parse_requirement_body(parent_body)['children']):
        raise IdentityError('work identity lacks reciprocal canonical linkage')
    validate(value, child=True)
    claims = {source: body}
    for sibling in requirement_intake.parse_requirement_body(parent_body)['children']:
        if sibling not in claims:
            claims[sibling] = str(managed_task.fetch_issue(root, *managed_task.issue_ref(sibling)).get('body') or '')
    assignments(parent_body, parent, claims)
    if recorded is not None and validate(recorded, child=True) != value:
        raise IdentityError('work identity disagrees with committed provenance')
    return value


BLOCK_START = '<!-- dev-platform:br-identity -->'
BLOCK_END = '<!-- /dev-platform:br-identity -->'


def presentation(title: str, body: str, identity: str, children: list[str] | None = None) -> tuple[str, str]:
    validate(identity, child=children is None)
    if children is not None:
        if not children or len(set(children)) != len(children):
            raise IdentityError('missing or duplicate shared child identity')
        for child in children:
            if not validate(child, child=True).startswith(identity + '/T'):
                raise IdentityError('shared child identity disagrees with parent')
    title = re.sub(r'^\[BR-[1-9][0-9]*(?:/T[1-9][0-9]*)?\]\s*', '', title)
    block = f'{BLOCK_START}\nWork identity: {identity}\n'
    if children is not None:
        block += 'Included children: ' + ', '.join(children) + '\n'
    block += BLOCK_END
    if BLOCK_START in body or BLOCK_END in body:
        if body.count(BLOCK_START) != 1 or body.count(BLOCK_END) != 1 or body.index(BLOCK_START) > body.index(BLOCK_END):
            raise IdentityError('malformed standard BR identity block')
        start, end = body.index(BLOCK_START), body.index(BLOCK_END) + len(BLOCK_END)
        body = body[:start] + block + body[end:]
    else:
        body += ('\n\n' if body else '') + block
    return f'[{identity}] {title}', body
