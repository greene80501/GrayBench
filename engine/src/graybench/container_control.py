"""Persistent local Docker control connection; never exposed to candidate containers."""

import json
import os
import subprocess

import docker

from graybench.artifacts import MAX_ARTIFACT_BYTES, ArtifactUnsupported, read_archive, validate_name


class ContainerControl:
    def __init__(self, executable):
        endpoint = os.environ.get("DOCKER_HOST")
        if not endpoint:
            result = subprocess.run(
                [executable, "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
                capture_output=True,
                check=True,
                timeout=15,
            )
            endpoint = json.loads(result.stdout)
        if not isinstance(endpoint, str) or not endpoint.startswith(("unix://", "npipe://")):
            raise RuntimeError("Candidate control requires a local Docker socket or named pipe")
        self.client = docker.APIClient(base_url=endpoint, version="auto", timeout=15)

    def pause(self, name):
        self.client.pause(name)

    def unpause(self, name):
        self.client.unpause(name)

    def create_workspace(self, name):
        self.client.create_volume(
            name=name,
            driver="local",
            driver_opts={
                "type": "tmpfs",
                "device": "tmpfs",
                "o": "size=256m,mode=1777,nosuid,nodev",
            },
            labels={"graybench": "ephemeral-candidate-workspace"},
        )

    def remove_workspace(self, name):
        try:
            self.client.remove_volume(name)
        except docker.errors.NotFound:
            pass  # An already-absent temporary volume satisfies cleanup.

    def capture_artifact(self, container, name, *, limit=MAX_ARTIFACT_BYTES):
        validate_name(name)
        if type(limit) is not int or not 0 < limit <= MAX_ARTIFACT_BYTES:
            raise ValueError("Invalid artifact byte limit")
        state = self.client.inspect_container(container)["State"]
        if not state.get("Running") or not state.get("Paused"):
            raise RuntimeError("Artifact capture requires a running paused container")
        try:
            chunks, stat = self.client.get_archive(container, "/tmp/" + name, chunk_size=65536)
        except docker.errors.NotFound as exc:
            # A vanished container is an infrastructure failure, not a missing candidate file.
            self.client.inspect_container(container)
            raise FileNotFoundError(name) from exc
        try:
            if stat.get("linkTarget") or stat.get("size", limit + 1) > limit:
                raise ArtifactUnsupported("Artifact is a link or exceeds byte limit")
            return read_archive(name, chunks, limit=limit)
        finally:
            chunks.close()

    def close(self):
        self.client.close()
