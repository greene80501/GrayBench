"""Bounded opaque output capture. Never extract archives or deserialize candidate files."""

import hashlib
import io
import re
import tarfile
from dataclasses import dataclass

MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
ARCHIVE_OVERHEAD = 64 * 1024


class ArtifactUnsupported(ValueError):
    """The file interface cannot be represented faithfully within these bounds."""


def validate_name(name):
    # A single file in the candidate workdir: no traversal, parent symlinks or host paths.
    if type(name) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
        raise ArtifactUnsupported("Expected a single relative artifact filename")
    return name


@dataclass(frozen=True)
class CapturedArtifact:
    name: str
    data: bytes

    @property
    def manifest(self):
        return {
            "name": self.name,
            "size": len(self.data),
            "sha256": hashlib.sha256(self.data).hexdigest(),
            "capture": "paused-docker-archive-v1",
        }


def read_archive(name, chunks, *, limit=MAX_ARTIFACT_BYTES):
    """Read one regular file as bytes, without writing any candidate-selected path."""
    validate_name(name)
    if type(limit) is not int or not 0 < limit <= MAX_ARTIFACT_BYTES:
        raise ValueError("Invalid artifact byte limit")
    archive = bytearray()
    for chunk in chunks:
        if len(archive) + len(chunk) > limit + ARCHIVE_OVERHEAD:
            raise ArtifactUnsupported("Artifact archive exceeds transport limit")
        archive.extend(chunk)
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as container:
            member = container.next()
            if (
                member is None
                or member.name != name
                or member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE)
                or member.issparse()
                or member.size < 0
                or member.size > limit
            ):
                raise ArtifactUnsupported("Expected one bounded regular artifact file")
            with container.extractfile(member) as stream:
                data = stream.read(limit + 1)
            if len(data) != member.size or container.next() is not None:
                raise ArtifactUnsupported("Invalid artifact archive contents")
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise ArtifactUnsupported("Invalid artifact archive") from exc
    return CapturedArtifact(name, data)
