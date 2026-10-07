"""Public, explicitly value-based call contracts for protected semantic tasks."""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from graybench.contracts import Contract, ExtractionPolicy, PublicTask

HEX = re.compile(r"[0-9a-f]{64}\Z")


class ValueShape(Contract):
    kind: Literal["null", "boolean", "integer", "number", "string", "array", "object"]
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)
    max_length: int = Field(default=65536, ge=0, le=1048576)
    min_items: int = Field(default=0, ge=0, le=10000)
    max_items: int = Field(default=10000, ge=0, le=10000)
    item: ValueShape | None = None
    properties: dict[str, ValueShape] = Field(default_factory=dict)
    required: tuple[str, ...] = ()

    @model_validator(mode="after")
    def consistent_shape(self) -> ValueShape:
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Value range is reversed")
        if self.min_items > self.max_items:
            raise ValueError("Value item bounds are reversed")
        if self.kind == "array" and self.item is None:
            raise ValueError("Array values require an item shape")
        if self.kind != "array" and self.item is not None:
            raise ValueError("Item shape only applies to arrays")
        if self.kind != "object" and (self.properties or self.required):
            raise ValueError("Properties only apply to objects")
        if self.kind == "object" and (
            len(set(self.required)) != len(self.required)
            or set(self.required) - set(self.properties)
        ):
            raise ValueError("Object required keys must be unique declared properties")
        if self.kind not in {"integer", "number"} and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("Numeric bounds only apply to numeric values")
        return self


class ValueCall(Contract):
    args: tuple[JsonValue, ...] = ()
    kwargs: dict[str, JsonValue] = Field(default_factory=dict)


class ProtectedValueContract(Contract):
    schema_version: Literal["1"] = "1"
    track: Literal["graybench-protected-semantic-v1"] = "graybench-protected-semantic-v1"
    source_task_digest: str
    public: PublicTask
    positional: tuple[ValueShape, ...]
    keywords: dict[str, ValueShape] = Field(default_factory=dict)
    result: ValueShape
    extraction: ExtractionPolicy = "raw_or_single_python_fence_v1"

    @model_validator(mode="after")
    def valid_contract(self) -> ProtectedValueContract:
        if not HEX.fullmatch(self.source_task_digest):
            raise ValueError("Protected value task requires pinned source identity")
        if set(self.keywords) & {"args", "kwargs"}:
            raise ValueError("Reserved call field name")
        return self


def validate_value(value: JsonValue, shape: ValueShape, *, depth: int = 0, budget=None) -> None:
    """Accept only finite JSON values of the exact declared recursive shape."""
    if budget is None:
        budget = [10000]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise ValueError("Value structural limit exceeded")
    kind = shape.kind
    if kind == "null":
        valid = value is None
    elif kind == "boolean":
        valid = type(value) is bool
    elif kind == "integer":
        valid = type(value) is int
    elif kind == "number":
        valid = type(value) is int or (type(value) is float and math.isfinite(value))
    elif kind == "string":
        valid = type(value) is str and len(value) <= shape.max_length
        if valid:
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("Value contains invalid Unicode") from exc
    elif kind == "array":
        valid = type(value) is list and shape.min_items <= len(value) <= shape.max_items
        if valid:
            for item in value:
                validate_value(item, shape.item, depth=depth + 1, budget=budget)
    else:
        valid = (
            type(value) is dict
            and shape.min_items <= len(value) <= shape.max_items
            and set(shape.required) <= set(value)
            and set(value) <= set(shape.properties)
        )
        if valid:
            for key, item in value.items():
                if type(key) is not str:
                    raise ValueError("JSON object keys must be strings")
                try:
                    key.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise ValueError("JSON object key contains invalid Unicode") from exc
                validate_value(item, shape.properties[key], depth=depth + 1, budget=budget)
    if not valid:
        raise ValueError("Value does not match declared " + kind + " shape")
    if kind in {"integer", "number"} and (
        (shape.minimum is not None and value < shape.minimum)
        or (shape.maximum is not None and value > shape.maximum)
    ):
        raise ValueError("Value is outside declared numeric range")
