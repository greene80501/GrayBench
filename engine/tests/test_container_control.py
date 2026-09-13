import pytest

from graybench.container_control import ContainerControl


def test_lifecycle_reuses_one_client_without_launching_commands(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "unix:///fixture.sock")
    calls = []

    class Client:
        def pause(self, name):
            calls.append(("pause", name))

        def unpause(self, name):
            calls.append(("unpause", name))

        def close(self):
            calls.append(("close",))

    clients = []

    def construct(**kwargs):
        clients.append(kwargs)
        return Client()

    monkeypatch.setattr("graybench.container_control.docker.APIClient", construct)
    monkeypatch.setattr(
        "graybench.container_control.subprocess.run",
        lambda *_a, **_k: pytest.fail("No CLI calls needed for explicit local endpoint"),
    )
    control = ContainerControl("docker")
    for _ in range(10):
        control.pause("candidate")
        control.unpause("candidate")
    control.close()
    assert len(clients) == 1
    assert len(calls) == 21
    assert clients[0]["timeout"] == 15


def test_remote_control_endpoint_is_not_silently_selected(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2375")
    with pytest.raises(RuntimeError, match="local"):
        ContainerControl("docker")
