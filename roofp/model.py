from __future__ import annotations

from dataclasses import dataclass, field


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


def build_analysis(request: PlotRequest) -> dict:
    """Produce a machine-readable analysis dict for the plot request."""
    ridge = request.ideal.ridge_point
    roof_compute = request.ideal.compute
    roof_bw = request.ideal.bandwidth

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
        operators.append({
            "name": op.name,
            "compute_flops": op.compute,
            "bandwidth_bytes": op.bandwidth,
            "arithmetic_intensity_flop_per_byte": ai,
            "attainable_performance_flops": op.compute,
            "bound": bound,
            "ridge_ratio": ai / ridge,
            "roof_performance_flops": roof_perf,
            "headroom_ratio": op.compute / roof_perf if roof_perf else None,
        })

    return {
        "title": request.title,
        "roofs": roofs,
        "operators": operators,
    }
