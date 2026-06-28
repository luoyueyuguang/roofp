from __future__ import annotations

import re
from typing import Any


_QUANTITY_RE = re.compile(
    r"^\s*(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(?P<unit>[A-Za-z/ ]*)\s*$"
)

_SI_PREFIXES = {
    "": 1.0,
    "k": 1e3,
    "m": 1e6,
    "g": 1e9,
    "t": 1e12,
    "p": 1e15,
    "e": 1e18,
}

_BINARY_PREFIXES = {
    "ki": 1024.0,
    "mi": 1024.0**2,
    "gi": 1024.0**3,
    "ti": 1024.0**4,
    "pi": 1024.0**5,
    "ei": 1024.0**6,
}


def parse_compute(value: Any) -> float:
    """Parse compute throughput into FLOP/s."""
    numeric, unit = _split_quantity(value, default_unit="flop/s")
    normalized = _normalize_unit(unit)

    for suffix in ("flop/s", "flops/s", "flopps"):
        if normalized.endswith(suffix):
            prefix = normalized[: -len(suffix)]
            return numeric * _decimal_multiplier(prefix, unit)

    for suffix in ("flops", "flop"):
        if normalized.endswith(suffix):
            prefix = normalized[: -len(suffix)]
            return numeric * _decimal_multiplier(prefix, unit)

    raise ValueError(
        f"Unsupported compute unit {unit!r}. Examples: FLOP/s, GFLOP/s, TFLOP/s."
    )


def parse_bandwidth(value: Any) -> float:
    """Parse memory bandwidth into Byte/s."""
    numeric, unit = _split_quantity(value, default_unit="byte/s")
    normalized = _normalize_unit(unit)

    for suffix in ("byte/s", "bytes/s"):
        if normalized.endswith(suffix):
            prefix = normalized[: -len(suffix)]
            return numeric * _byte_multiplier(prefix, unit)

    if normalized.endswith("b/s"):
        prefix = normalized[:-3]
        return numeric * _byte_multiplier(prefix, unit)

    if normalized.endswith("bps"):
        prefix = normalized[:-3]
        return numeric * _byte_multiplier(prefix, unit)

    raise ValueError(
        f"Unsupported bandwidth unit {unit!r}. Examples: B/s, GB/s, GiB/s, TB/s."
    )



def _is_plain_number(s: str) -> bool:
    """Check if string is a plain numeric value (no unit)."""
    try:
        float(s)
        return True
    except ValueError:
        return False

def parse_arithmetic_intensity(value: Any) -> float:
    """Parse arithmetic intensity into FLOP/Byte.

    Accepts:
    - plain number: 3.25
    - unit string: "3.25 FLOP/Byte"
    - ratio with units: "650 GFLOP/s / 200 GB/s"
    - bare ratio: "650/200"
    """
    if isinstance(value, str):
        # ratio format: "A / B" or "A/B"
        stripped = value.strip()
        if "/" in stripped:
            # try split on " / " first, then bare "/"
            sep = " / " if " / " in stripped else "/"
            parts = [p.strip() for p in stripped.rsplit(sep, 1)]
            if len(parts) == 2:
                left, right = parts
                # bare numbers
                if _is_plain_number(left) and _is_plain_number(right):
                    return float(left) / float(right)
                # units on both sides
                try:
                    return parse_compute(left) / parse_bandwidth(right)
                except ValueError:
                    pass  # fall through to standard parse

    numeric, unit = _split_quantity(value, default_unit="flop/byte")
    normalized = _normalize_unit(unit)

    for suffix in ("flop/byte", "flops/byte", "flop/bytes", "flops/bytes"):
        if normalized.endswith(suffix):
            return numeric

    raise ValueError(
        f"Unsupported arithmetic intensity unit {unit!r}. "
        "Examples: 3.25, \"3.25 FLOP/Byte\", \"650/200\", \"650 GFLOP/s / 200 GB/s\"."
    )


def _split_quantity(value: Any, default_unit: str) -> tuple[float, str]:
    if isinstance(value, int | float):
        return float(value), default_unit

    if isinstance(value, str):
        match = _QUANTITY_RE.match(value)
        if not match:
            raise ValueError(f"Invalid quantity {value!r}")
        unit = match.group("unit") or default_unit
        return float(match.group("value")), unit

    if isinstance(value, dict):
        if "value" not in value:
            raise ValueError(f"Quantity object requires a value field: {value!r}")
        return float(value["value"]), str(value.get("unit", default_unit))

    raise ValueError(f"Unsupported quantity value {value!r}")


def _normalize_unit(unit: str) -> str:
    return unit.lower().replace(" ", "").replace("per", "/")


def _decimal_multiplier(prefix: str, original_unit: str) -> float:
    if prefix in _SI_PREFIXES:
        return _SI_PREFIXES[prefix]
    raise ValueError(f"Unsupported decimal prefix in unit {original_unit!r}")


def _byte_multiplier(prefix: str, original_unit: str) -> float:
    if prefix in _BINARY_PREFIXES:
        return _BINARY_PREFIXES[prefix]
    if prefix in _SI_PREFIXES:
        return _SI_PREFIXES[prefix]
    raise ValueError(f"Unsupported byte prefix in unit {original_unit!r}")
