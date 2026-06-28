from __future__ import annotations

from dataclasses import dataclass, field
import math


def _validate_positive(name: str, value: float) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class RoofSpec:
    label: str
    compute: float
    bandwidth: float
    color: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "compute", _validate_positive("compute", self.compute))
        object.__setattr__(
            self, "bandwidth", _validate_positive("bandwidth", self.bandwidth)
        )

    @property
    def ridge_point(self) -> float:
        return self.compute / self.bandwidth


@dataclass(frozen=True)
class OperatorPoint:
    name: str
    compute: float
    bandwidth: float
    color: str = "#1f2937"

    def __post_init__(self) -> None:
        object.__setattr__(self, "compute", _validate_positive("compute", self.compute))
        object.__setattr__(
            self, "bandwidth", _validate_positive("bandwidth", self.bandwidth)
        )

    @property
    def arithmetic_intensity(self) -> float:
        return self.compute / self.bandwidth


_OPERATOR_COLORS = [
    "#7c3aed",  # violet
    "#059669",  # emerald
    "#d97706",  # amber
    "#db2777",  # pink
    "#0891b2",  # cyan
    "#65a30d",  # lime
]



@dataclass(frozen=True)
class PlotRequest:
    title: str
    ideal: RoofSpec
    actual: RoofSpec | None = None
    operators: list[OperatorPoint] = field(default_factory=list)
    width: int = 1280
    height: int = 720

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")

    @property
    def roofs(self) -> list[RoofSpec]:
        roofs = [self.ideal]
        if self.actual is not None:
            roofs.append(self.actual)
        return roofs


def _format_si(value: float, unit: str) -> str:
    """Format a value with SI prefix, e.g. 1.2e12 → '1.20 T' + unit."""
    if value == 0:
        return f"0 {unit}"
    prefixes = ["", "k", "M", "G", "T", "P", "E"]
    exponent = int(math.log10(abs(value)) // 3)
    exponent = max(0, min(exponent, len(prefixes) - 1))
    scaled = value / 10 ** (exponent * 3)
    return f"{scaled:.3g} {prefixes[exponent]}{unit}"


def build_analysis(request: PlotRequest) -> dict:
    """Produce a machine-readable analysis dict for the plot request."""
    ridge = request.ideal.ridge_point
    roof_compute = request.ideal.compute
    roof_bw = request.ideal.bandwidth

    roof_desc = (
        f"Ideal roof: peak compute = {_format_si(roof_compute, 'FLOP/s')}, "
        f"bandwidth = {_format_si(roof_bw, 'Byte/s')}, "
        f"ridge point = {_format_si(ridge, 'FLOP/Byte')}"
    )

    roofs: dict[str, dict] = {
        "ideal": {
            "label": request.ideal.label,
            "compute_flops": roof_compute,
            "bandwidth_bytes": roof_bw,
            "ridge_point_flop_per_byte": ridge,
        }
    }
    if request.actual is not None:
        roofs["actual"] = {
            "label": request.actual.label,
            "compute_flops": request.actual.compute,
            "bandwidth_bytes": request.actual.bandwidth,
            "ridge_point_flop_per_byte": request.actual.ridge_point,
        }

    operators = []
    for op in request.operators:
        ai = op.arithmetic_intensity
        roof_perf = min(roof_compute, roof_bw * ai)
        if ai < ridge:
            bound = "memory"
        elif ai > ridge:
            bound = "compute"
        else:
            bound = "ridge"
        headroom = op.compute / roof_perf if roof_perf else None
        ridge_ratio = ai / ridge

        if bound == "memory":
            bound_desc = "memory-bound (limited by bandwidth)"
        elif bound == "compute":
            bound_desc = "compute-bound (limited by peak FLOP/s)"
        else:
            bound_desc = "at ridge point"

        pct = f"{headroom * 100:.1f}%" if headroom is not None else "N/A"
        description = (
            f"{op.name}: {_format_si(op.compute, 'FLOP/s')} "
            f"at arithmetic intensity {_format_si(ai, 'FLOP/Byte')}, "
            f"{bound_desc}, "
            f"{ridge_ratio:.2f}× ridge point, "
            f"reaches {pct} of ideal roofline ceiling"
        )

        operators.append({
            "name": op.name,
            "compute_flops": op.compute,
            "bandwidth_bytes": op.bandwidth,
            "arithmetic_intensity_flop_per_byte": ai,
            "attainable_performance_flops": op.compute,
            "bound": bound,
            "ridge_ratio": ridge_ratio,
            "roof_performance_flops": roof_perf,
            "headroom_ratio": headroom,
            "description": description,
        })

    return {
        "title": request.title,
        "roof_description": roof_desc,
        "roofs": roofs,
        "operators": operators,
    }
