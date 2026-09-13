"""Reported uncertainty describes task sampling, not hidden dataset correctness."""

from math import sqrt


def wilson_interval(passed: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0 or not 0 <= passed <= total:
        raise ValueError("Expected 0 <= passed <= total and total > 0")
    p = passed / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)
