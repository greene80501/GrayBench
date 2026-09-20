"""Closed protocol4 roots and basic value-exception contract."""

from graybench.circuit_wire import WireError, fields

EXCEPTIONS = {
    cls.__name__: cls
    for cls in (
        ValueError,
        TypeError,
        RuntimeError,
        AssertionError,
        KeyError,
        IndexError,
        ZeroDivisionError,
        OverflowError,
        NotImplementedError,
    )
}


def exception_name(exc):
    name = type(exc).__name__
    if (
        EXCEPTIONS.get(name) is not type(exc)
        or vars(exc)
        or exc.__cause__ is not None
        or exc.__context__ is not None
        or exc.__suppress_context__
    ):
        raise WireError("Exception metadata or class requires a further graph capability")
    return name


def validate_roots(wire, names):
    if type(wire) is not dict:
        raise WireError("Expected graph envelope")
    fields(wire.get("roots"), names)


def validate_arguments(roots):
    if type(roots["args"]) is not tuple or type(roots["kwargs"]) is not dict:
        raise WireError("Invalid call argument roots")
    if any(type(key) is not str for key in roots["kwargs"]):
        raise WireError("Invalid keyword argument name")


def validate_root_shapes(wire, *, response=False, raised=None):
    """Call only after arena.prepare validated records, before any live commit."""
    index = {record["id"]: record for record in wire["nodes"]}
    roots = wire["roots"]

    def require(name, kind):
        token = roots[name]
        if type(token) is not dict or set(token) != {"ref"}:
            raise WireError("Call root must reference a graph node")
        if index[token["ref"]]["kind"] != kind:
            raise WireError("Invalid graph call root kind")
        return index[token["ref"]]["state"]

    require("args", "tuple")
    kwargs = require("kwargs", "dict")
    if any(type(key) is not str for key, _ in kwargs):
        raise WireError("Invalid keyword argument name")
    if response:
        if raised is None:
            if roots["exception_args"] is not None:
                raise WireError("Unexpected exception arguments")
        else:
            require("exception_args", "tuple")
            if roots["result"] is not None:
                raise WireError("Exception response cannot have a result")
