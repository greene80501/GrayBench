import io
import os
import tarfile

import pytest

from graybench.artifacts import ArtifactUnsupported, read_archive, validate_name
from graybench.sandbox import Candidate


def archive(name="answer.bin", data=b"\x00\xffpayload", kind=tarfile.REGTYPE, extra=False):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w") as out:
        member = tarfile.TarInfo(name)
        member.type = kind
        member.linkname = "/judge/task.json" if kind == tarfile.SYMTYPE else ""
        member.size = len(data) if kind == tarfile.REGTYPE else 0
        out.addfile(member, io.BytesIO(data))
        if extra:
            out.addfile(tarfile.TarInfo("other"))
    return result.getvalue()


def test_capture_preserves_opaque_bytes_with_content_digest():
    result = read_archive("answer.bin", [archive()])
    assert result.data == b"\x00\xffpayload"
    assert result.manifest["size"] == 9
    assert len(result.manifest["sha256"]) == 64


@pytest.mark.parametrize("name", ["../answer", "/tmp/answer", "dir/answer", "a\\b", "", ".", ".."])
def test_candidate_paths_cannot_select_other_locations(name):
    with pytest.raises(ArtifactUnsupported):
        validate_name(name)


@pytest.mark.parametrize(
    "payload",
    [
        archive(name="../answer.bin"),
        archive(kind=tarfile.SYMTYPE),
        archive(kind=tarfile.LNKTYPE),
        archive(kind=tarfile.FIFOTYPE),
        archive(kind=tarfile.DIRTYPE),
        archive(extra=True),
        b"not an archive",
    ],
    ids=["traversal", "symlink", "hardlink", "fifo", "directory", "extra", "invalid"],
)
def test_reject_unsafe_or_ambiguous_archive(payload):
    with pytest.raises(ArtifactUnsupported):
        read_archive("answer.bin", [payload])


def test_file_and_archive_caps_are_independent():
    with pytest.raises(ArtifactUnsupported):
        read_archive("answer.bin", [archive(data=b"x" * 11)], limit=10)
    with pytest.raises(ArtifactUnsupported):
        read_archive("answer.bin", [b"x" * 70000], limit=10)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
def test_real_capture_is_paused_opaque_and_rejects_links_missing_and_oversized_files():
    code = """from pathlib import Path
def answer():
    Path('answer.bin').write_bytes(b'\\x00\\xffpayload')
    Path('linked.bin').symlink_to('/input/candidate.py')
    Path('big.bin').write_bytes(b'x'*100)
"""
    with Candidate(
        code,
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
    ) as candidate:
        candidate.call("answer")
        assert candidate.paused
        captured = candidate.capture_artifact("answer.bin")
        assert captured.data == b"\x00\xffpayload"
        assert candidate.paused
        volume_name = candidate.workspace
        control = candidate.control
        assert control.client.inspect_volume(volume_name)["Options"]["type"] == "tmpfs"
        with pytest.raises(ArtifactUnsupported):
            candidate.capture_artifact("linked.bin")
        with pytest.raises(ArtifactUnsupported):
            candidate.capture_artifact("big.bin", limit=10)
        with pytest.raises(FileNotFoundError):
            candidate.capture_artifact("absent.bin")
    with pytest.raises(RuntimeError):
        candidate.capture_artifact("answer.bin")
    import docker

    with pytest.raises(docker.errors.NotFound):
        control.client.inspect_volume(volume_name)
