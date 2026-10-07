"""SDK-independent graph resource contract shared by host and protected runtimes."""

from dataclasses import asdict, dataclass

from graybench.circuit_wire import WireError, fields


@dataclass(frozen=True)
class GraphLimits:
    nodes: int = 100_000
    edges: int = 100_000
    message_bytes: int = 1_048_576
    array_bytes: int = 524_288
    matrix_bytes: int = 524_288
    depth: int = 32

    def __post_init__(self):
        ceilings = dict(
            nodes=100_000,
            edges=100_000,
            message_bytes=16_777_216,
            array_bytes=16_777_216,
            matrix_bytes=16_777_216,
            depth=128,
        )
        if any(
            type(getattr(self, key)) is not int or not 1 <= getattr(self, key) <= maximum
            for key, maximum in ceilings.items()
        ):
            raise WireError("Invalid graph resource limit")

    def record(self):
        return asdict(self)

    @classmethod
    def from_record(cls, record):
        fields(record, {"nodes", "edges", "message_bytes", "array_bytes", "matrix_bytes", "depth"})
        return cls(**record)


def transport_record(mode, wire_bytes, state_bytes=None):
    """Freeze wire and expanded-state bounds without importing the SDK."""
    if type(mode) is not str or mode not in ("snapshot-v1", "delta-v1"):
        raise WireError("Unknown graph transport")
    state_bytes = wire_bytes if state_bytes is None else state_bytes
    GraphLimits(message_bytes=wire_bytes)
    GraphLimits(message_bytes=state_bytes)
    if mode == "snapshot-v1" and state_bytes != wire_bytes:
        raise WireError("Snapshot transport requires equal wire and state byte limits")
    return {"mode": mode, "wire_bytes": wire_bytes, "state_bytes": state_bytes}


def validate_transport(record):
    fields(record, {"mode", "wire_bytes", "state_bytes"})
    return transport_record(record["mode"], record["wire_bytes"], record["state_bytes"])
