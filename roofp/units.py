from __future__ import annotations

import math
import re
from collections.abc import Callable
from typing import Any

_NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_QUANTITY_RE = re.compile(rf"^\s*(?P<value>{_NUMBER_PATTERN})\s*(?P<unit>[A-Za-z/ ]*)\s*$")

_DECIMAL_PREFIXES = {
    "": 1.0,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
    "T": 1e12,
    "P": 1e15,
    "E": 1e18,
}

_BINARY_PREFIXES = {
    "Ki": 1024.0,
    "Mi": 1024.0**2,
    "Gi": 1024.0**3,
    "Ti": 1024.0**4,
    "Pi": 1024.0**5,
    "Ei": 1024.0**6,
}


def parse_compute(value: Any) -> float:
    """Parse compute throughput into FLOP/s using case-sensitive SI prefixes."""
    numeric, unit = _split_quantity(value, default_unit="FLOP/s")
    compact = _compact_unit(unit)
    lower = compact.lower()

    for suffix in ("flop/s", "flops/s"):
        if lower.endswith(suffix):
            prefix = compact[: -len(suffix)]
            return _validate_quantity(
                "compute",
                numeric * _decimal_multiplier(prefix, unit),
            )

    # GFLOPS is a common abbreviation for GFLOP/s. Bare FLOP is intentionally
    # rejected because it is an operation count, not a throughput.
    if lower.endswith("flops"):
        prefix = compact[:-5]
        return _validate_quantity(
            "compute",
            numeric * _decimal_multiplier(prefix, unit),
        )

    if lower.endswith("flop"):
        raise ValueError(
            f"Compute unit {unit!r} is an operation count, not a throughput. "
            "Use FLOP/s, for example GFLOP/s or TFLOP/s."
        )

    raise ValueError(f"Unsupported compute unit {unit!r}. Examples: FLOP/s, GFLOP/s, TFLOP/s.")


def parse_bandwidth(value: Any) -> float:
    """Parse memory bandwidth into Byte/s, preserving bit/byte case semantics."""
    numeric, unit = _split_quantity(value, default_unit="Byte/s")
    compact = _compact_unit(unit)
    lower = compact.lower()

    for suffix in ("byte/s", "bytes/s"):
        if lower.endswith(suffix):
            prefix = compact[: -len(suffix)]
            return _validate_quantity(
                "bandwidth",
                numeric * _byte_multiplier(prefix, unit),
            )

    if compact.endswith("B/s"):
        prefix = compact[:-3]
        return _validate_quantity(
            "bandwidth",
            numeric * _byte_multiplier(prefix, unit),
        )

    if compact.endswith("Bps"):
        prefix = compact[:-3]
        return _validate_quantity(
            "bandwidth",
            numeric * _byte_multiplier(prefix, unit),
        )

    if compact.endswith("b/s") or lower.endswith("bps"):
        raise ValueError(
            f"Bit-rate unit {unit!r} is not supported. Use Byte/s or B/s, for example GB/s."
        )

    raise ValueError(f"Unsupported bandwidth unit {unit!r}. Examples: B/s, GB/s, GiB/s, TB/s.")


def parse_arithmetic_intensity(value: Any) -> float:
    """Parse arithmetic intensity into FLOP/Byte."""
    direct = _try_parse_direct_intensity(value)
    if direct is not None:
        return direct

    if isinstance(value, str):
        stripped = value.strip()
        bare_ratio = re.fullmatch(
            rf"\s*(?P<numerator>{_NUMBER_PATTERN})\s*/\s*"
            rf"(?P<denominator>{_NUMBER_PATTERN})\s*",
            stripped,
        )
        if bare_ratio:
            numerator = _validate_quantity(
                "ratio numerator",
                float(bare_ratio.group("numerator")),
            )
            denominator = _validate_quantity(
                "ratio denominator",
                float(bare_ratio.group("denominator")),
            )
            return _validate_quantity(
                "arithmetic_intensity",
                numerator / denominator,
            )

        ratio = _try_parse_quantity_ratio(stripped, parse_compute, parse_bandwidth)
        if ratio is not None:
            return _validate_quantity("arithmetic_intensity", ratio)

    raise ValueError(
        f"Unsupported arithmetic intensity value {value!r}. Examples: 3.25, "
        '"3.25 FLOP/Byte", "650/200", or '
        '"650 GFLOP/s / 200 GB/s".'
    )


def _try_parse_direct_intensity(value: Any) -> float | None:
    if isinstance(value, bool):
        raise ValueError(f"Unsupported quantity value {value!r}")
    if isinstance(value, int | float):
        return _validate_quantity("arithmetic_intensity", float(value))
    if isinstance(value, dict):
        numeric, unit = _split_quantity(value, default_unit="FLOP/Byte")
        if _is_intensity_unit(unit):
            return _validate_quantity("arithmetic_intensity", numeric)
        return None
    if not isinstance(value, str):
        return None

    match = _QUANTITY_RE.fullmatch(value)
    if not match:
        return None
    unit = match.group("unit") or "FLOP/Byte"
    if not _is_intensity_unit(unit):
        return None
    return _validate_quantity(
        "arithmetic_intensity",
        float(match.group("value")),
    )


def _try_parse_quantity_ratio(
    value: str,
    numerator_parser: Callable[[str], float],
    denominator_parser: Callable[[str], float],
) -> float | None:
    # Try every slash as the top-level ratio separator. Unit-internal slashes
    # fail one of the typed parsers, while the actual separator succeeds.
    for index, character in enumerate(value):
        if character != "/":
            continue
        left = value[:index].strip()
        right = value[index + 1 :].strip()
        if not left or not right:
            continue
        try:
            numerator = numerator_parser(left)
            denominator = denominator_parser(right)
        except ValueError:
            continue
        return numerator / denominator
    return None


def _is_intensity_unit(unit: str) -> bool:
    normalized = _compact_unit(unit).lower()
    return normalized in {
        "flop/byte",
        "flops/byte",
        "flop/bytes",
        "flops/bytes",
    }


def _split_quantity(value: Any, default_unit: str) -> tuple[float, str]:
    if isinstance(value, bool):
        raise ValueError(f"Unsupported quantity value {value!r}")

    if isinstance(value, int | float):
        return float(value), default_unit

    if isinstance(value, str):
        match = _QUANTITY_RE.fullmatch(value)
        if not match:
            raise ValueError(f"Invalid quantity {value!r}")
        unit = match.group("unit") or default_unit
        return float(match.group("value")), unit

    if isinstance(value, dict):
        if "value" not in value:
            raise ValueError(f"Quantity object requires a value field: {value!r}")
        try:
            numeric = float(value["value"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid quantity value: {value!r}") from exc
        unit_value = value.get("unit", default_unit)
        if not isinstance(unit_value, str):
            raise ValueError(f"Quantity unit must be a string: {value!r}")
        return numeric, unit_value

    raise ValueError(f"Unsupported quantity value {value!r}")


def _compact_unit(unit: str) -> str:
    replaced = re.sub(r"\bper\b", "/", unit, flags=re.IGNORECASE)
    return re.sub(r"\s+", "", replaced)


def _validate_quantity(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be a finite positive number, got {value!r}")
    return numeric


def _decimal_multiplier(prefix: str, original_unit: str) -> float:
    if prefix in _DECIMAL_PREFIXES:
        return _DECIMAL_PREFIXES[prefix]
    if prefix == "m":
        raise ValueError(
            f"Ambiguous lowercase milli prefix in unit {original_unit!r}. Use uppercase M for mega."
        )
    raise ValueError(f"Unsupported decimal prefix in unit {original_unit!r}")


def _byte_multiplier(prefix: str, original_unit: str) -> float:
    if prefix in _BINARY_PREFIXES:
        return _BINARY_PREFIXES[prefix]
    if prefix in _DECIMAL_PREFIXES:
        return _DECIMAL_PREFIXES[prefix]
    if prefix == "m":
        raise ValueError(
            f"Ambiguous lowercase milli prefix in unit {original_unit!r}. Use uppercase M for mega."
        )
    raise ValueError(f"Unsupported byte prefix in unit {original_unit!r}")
