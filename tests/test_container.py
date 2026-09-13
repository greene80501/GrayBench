from graybench.execution.container import command


def test_container_cannot_reach_network_or_mount_provider_configuration(tmp_path):
    args = command("sha256:example", tmp_path, "graybench-test")
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert args[args.index("--user") + 1] == "65534:65534"
    mounts = [args[i + 1] for i, value in enumerate(args) if value == "--mount"]
    assert mounts == [f"type=bind,source={tmp_path.resolve()},target=/input,readonly"]
    assert not any("API_KEY" in arg or ".env" in arg for arg in args)
