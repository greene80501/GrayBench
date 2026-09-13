"""Persistent local Docker control connection; never exposed to candidate containers."""

import json
import os
import subprocess

import docker


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

    def close(self):
        self.client.close()
