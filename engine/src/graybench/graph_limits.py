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
            array_bytes=524_288,
            matrix_bytes=524_288,
            depth=32,
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
