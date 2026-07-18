from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

SCHEMA_VERSION = "2.0"
RELATIVE_TOLERANCE = 1e-9

ComputeKind = Literal["theoretical", "measured", "unspecified"]
BandwidthKind = Literal["theoretical", "sustained", "measured", "unspecified"]
BandwidthLevel = Literal[
    "dram",
    "hbm",
    "l2",
    "l1",
    "shared",
    "pcie",
    "nvlink",
    "other",
    "unspecified",
]

_COMPUTE_KINDS = {"theoretical", "measured", "unspecified"}
_BANDWIDTH_KINDS = {"theoretical", "sustained", "measured", "unspecified"}
_BANDWIDTH_LEVELS = {
    "dram",
    "hbm",
    "l2",
    "l1",
    "shared",
    "pcie",
    "nvlink",
    "other",
    "unspecified",
}


def _validate_positive(name: str, value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite positive number, got {value!r}")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite positive number, got {value!r}") from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be a finite positive number, got {value!r}")
    return numeric


def _validate_text(name: str, value: str, *, max_length: int = 512) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > max_length:
        raise ValueError(f"{name} must not exceed {max_length} characters")
    return value


def _validate_optional_text(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return _validate_text(name, value)


@dataclass(frozen=True)
class RoofSpec:
    label: str
    compute: float
    bandwidth: float
    color: str
    precision: str | None = None
    compute_kind: ComputeKind = "unspecified"
    bandwidth_level: BandwidthLevel = "unspecified"
    bandwidth_kind: BandwidthKind = "unspecified"
    fma_flop_count: int | None = None
    sparsity: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _validate_text("roof label", self.label))
        object.__setattr__(self, "color", _validate_text("roof color", self.color))
        object.__setattr__(self, "compute", _validate_positive("compute", self.compute))
        object.__setattr__(
            self,
            "bandwidth",
            _validate_positive("bandwidth", self.bandwidth),
        )
        object.__setattr__(
            self,
            "precision",
            _validate_optional_text("precision", self.precision),
        )
        object.__setattr__(
            self,
            "sparsity",
            _validate_optional_text("sparsity", self.sparsity),
        )
        object.__setattr__(
            self,
            "notes",
            _validate_optional_text("notes", self.notes),
        )
        if not isinstance(self.compute_kind, str) or self.compute_kind not in _COMPUTE_KINDS:
            raise ValueError(f"Unsupported compute_kind {self.compute_kind!r}")
        if not isinstance(self.bandwidth_kind, str) or self.bandwidth_kind not in _BANDWIDTH_KINDS:
            raise ValueError(f"Unsupported bandwidth_kind {self.bandwidth_kind!r}")
        if (
            not isinstance(self.bandwidth_level, str)
            or self.bandwidth_level not in _BANDWIDTH_LEVELS
        ):
            raise ValueError(f"Unsupported bandwidth_level {self.bandwidth_level!r}")
        if isinstance(self.fma_flop_count, bool) or self.fma_flop_count not in (None, 1, 2):
            raise ValueError("fma_flop_count must be 1, 2, or omitted")

    @property
    def ridge_point(self) -> float:
        return self.compute / self.bandwidth


@dataclass(frozen=True)
class OperatorPoint:
    name: str
    compute: float
    arithmetic_intensity: float
    color: str = "#1f2937"

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validate_text("operator name", self.name))
        object.__setattr__(self, "color", _validate_text("operator color", self.color))
        object.__setattr__(self, "compute", _validate_positive("compute", self.compute))
        object.__setattr__(
            self,
            "arithmetic_intensity",
            _validate_positive("arithmetic_intensity", self.arithmetic_intensity),
        )

    @property
    def bandwidth(self) -> float:
        """Return achieved bandwidth in Byte/s derived from performance and intensity."""
        return self.compute / self.arithmetic_intensity

    @classmethod
    def from_arithmetic_intensity(
        cls,
        *,
        name: str,
        compute: float,
        arithmetic_intensity: float,
        color: str = "#1f2937",
    ) -> OperatorPoint:
        """Build an operator from the public compute and intensity inputs."""
        return cls(
            name=name,
            compute=compute,
            arithmetic_intensity=arithmetic_intensity,
            color=color,
        )


@dataclass(frozen=True)
class RoofEvaluation:
    bound: Literal["memory", "compute", "ridge"]
    ridge_ratio: float
    roof_ceiling_flop_per_second: float
    utilization_ratio: float
    remaining_headroom_ratio: float
    above_roof: bool

    def to_dict(self) -> dict[str, float | str | bool]:
        return {
            "bound": self.bound,
            "ridge_ratio": self.ridge_ratio,
            "roof_ceiling_flop_per_second": self.roof_ceiling_flop_per_second,
            "utilization_ratio": self.utilization_ratio,
            "remaining_headroom_ratio": self.remaining_headroom_ratio,
            "above_roof": self.above_roof,
        }


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
    operators: tuple[OperatorPoint, ...] = field(default_factory=tuple)
    width: int = 1280
    height: int = 720
    additional_roofs: tuple[RoofSpec, ...] = field(default_factory=tuple)
    show_bound_regions: bool = True
    peer_roofs: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _validate_text("title", self.title))
        if not isinstance(self.ideal, RoofSpec):
            raise ValueError("ideal must be a RoofSpec")
        if self.actual is not None and not isinstance(self.actual, RoofSpec):
            raise ValueError("actual must be a RoofSpec or None")

        operators = tuple(self.operators)
        if not all(isinstance(operator, OperatorPoint) for operator in operators):
            raise ValueError("operators must contain only OperatorPoint values")
        object.__setattr__(self, "operators", operators)

        additional_roofs = tuple(self.additional_roofs)
        if not all(isinstance(roof, RoofSpec) for roof in additional_roofs):
            raise ValueError("additional_roofs must contain only RoofSpec values")
        object.__setattr__(self, "additional_roofs", additional_roofs)

        for name, value in (("width", self.width), ("height", self.height)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")
            if value > 16_384:
                raise ValueError(f"{name} must not exceed 16384, got {value!r}")
        if self.width * self.height > 100_000_000:
            raise ValueError("width * height must not exceed 100,000,000 pixels")
        if not isinstance(self.show_bound_regions, bool):
            raise ValueError("show_bound_regions must be a boolean")
        if not isinstance(self.peer_roofs, bool):
            raise ValueError("peer_roofs must be a boolean")

    @property
    def roofs(self) -> tuple[RoofSpec, ...]:
        roofs = [self.ideal]
        if self.actual is not None:
            roofs.append(self.actual)
        roofs.extend(self.additional_roofs)
        return tuple(roofs)


def classify_bound(
    arithmetic_intensity: float,
    ridge_point: float,
) -> Literal["memory", "compute", "ridge"]:
    if math.isclose(
        arithmetic_intensity,
        ridge_point,
        rel_tol=RELATIVE_TOLERANCE,
        abs_tol=0.0,
    ):
        return "ridge"
    return "memory" if arithmetic_intensity < ridge_point else "compute"


def evaluate_operator(roof: RoofSpec, operator: OperatorPoint) -> RoofEvaluation:
    arithmetic_intensity = operator.arithmetic_intensity
    roof_ceiling = min(roof.compute, roof.bandwidth * arithmetic_intensity)
    utilization = operator.compute / roof_ceiling
    at_roof = math.isclose(
        utilization,
        1.0,
        rel_tol=RELATIVE_TOLERANCE,
        abs_tol=0.0,
    )
    return RoofEvaluation(
        bound=classify_bound(arithmetic_intensity, roof.ridge_point),
        ridge_ratio=arithmetic_intensity / roof.ridge_point,
        roof_ceiling_flop_per_second=roof_ceiling,
        utilization_ratio=utilization,
        remaining_headroom_ratio=0.0 if at_roof else 1.0 - utilization,
        above_roof=utilization > 1.0 and not at_roof,
    )


def comparison_metadata_warnings(roofs: tuple[RoofSpec, ...]) -> list[str]:
    warnings: list[str] = []
    fields: dict[str, list[str]] = {
        "precision": [str(roof.precision) for roof in roofs if roof.precision],
        "bandwidth_level": [
            roof.bandwidth_level for roof in roofs if roof.bandwidth_level != "unspecified"
        ],
        "fma_flop_count": [
            str(roof.fma_flop_count) for roof in roofs if roof.fma_flop_count is not None
        ],
        "sparsity": [roof.sparsity for roof in roofs if roof.sparsity],
    }
    for field_name, values in fields.items():
        if len(set(values)) > 1:
            warnings.append(
                f"Compared roofs use different {field_name} values: "
                f"{', '.join(sorted(set(values)))}."
            )
    for field_name, values in fields.items():
        if values and len(values) != len(roofs):
            warnings.append(
                f"Some compared roofs omit {field_name}; verify that all inputs use "
                "the same measurement convention."
            )
    return warnings


def _format_si(value: float, unit: str) -> str:
    if value == 0:
        return f"0 {unit}"
    prefixes = ["", "k", "M", "G", "T", "P", "E"]
    exponent = int(math.log10(abs(value)) // 3)
    exponent = max(0, min(exponent, len(prefixes) - 1))
    scaled = value / 10 ** (exponent * 3)
    return f"{scaled:.3g} {prefixes[exponent]}{unit}"


def _roof_to_dict(roof: RoofSpec) -> dict[str, object]:
    return {
        "label": roof.label,
        "peak_compute_flop_per_second": roof.compute,
        "bandwidth_byte_per_second": roof.bandwidth,
        "ridge_point_flop_per_byte": roof.ridge_point,
        "metadata": {
            "precision": roof.precision,
            "compute_kind": roof.compute_kind,
            "bandwidth_level": roof.bandwidth_level,
            "bandwidth_kind": roof.bandwidth_kind,
            "fma_flop_count": roof.fma_flop_count,
            "sparsity": roof.sparsity,
            "notes": roof.notes,
        },
    }


def _evaluation_description(
    operator: OperatorPoint,
    roof: RoofSpec,
    evaluation: RoofEvaluation,
) -> str:
    bound_descriptions = {
        "memory": "memory-bound (limited by bandwidth)",
        "compute": "compute-bound (limited by peak FLOP/s)",
        "ridge": "at the ridge point",
    }
    prefix = (
        f"{operator.name} on {roof.label}: "
        f"{_format_si(operator.compute, 'FLOP/s')} at arithmetic intensity "
        f"{_format_si(operator.arithmetic_intensity, 'FLOP/Byte')}, "
        f"{bound_descriptions[evaluation.bound]}, "
        f"{evaluation.ridge_ratio:.2f}× ridge point"
    )
    if evaluation.above_roof:
        excess = (evaluation.utilization_ratio - 1.0) * 100
        return (
            f"{prefix}; exceeds the configured roofline ceiling by {excess:.1f}%. "
            "Verify peak values, units, precision, FLOP counting, and measurement "
            "accounting."
        )
    if math.isclose(
        evaluation.utilization_ratio,
        1.0,
        rel_tol=RELATIVE_TOLERANCE,
        abs_tol=0.0,
    ):
        return f"{prefix}; operates at the configured roofline ceiling."
    return (
        f"{prefix}; reaches {evaluation.utilization_ratio * 100:.1f}% of the "
        "configured roofline ceiling."
    )


def build_analysis(request: PlotRequest) -> dict[str, object]:
    """Produce schema-versioned, per-roof analysis for a plot request."""
    named_roofs: list[tuple[str, RoofSpec]] = [("ideal", request.ideal)]
    if request.actual is not None:
        named_roofs.append(("actual", request.actual))
    named_roofs.extend(
        (f"additional_{index}", roof) for index, roof in enumerate(request.additional_roofs)
    )

    operators: list[dict[str, object]] = []
    for operator in request.operators:
        evaluations = {
            key: evaluate_operator(roof, operator).to_dict() for key, roof in named_roofs
        }
        ideal_evaluation = evaluate_operator(request.ideal, operator)
        operators.append(
            {
                "name": operator.name,
                "measured_performance_flop_per_second": operator.compute,
                "achieved_bandwidth_byte_per_second": operator.bandwidth,
                "arithmetic_intensity_flop_per_byte": operator.arithmetic_intensity,
                "evaluations": evaluations,
                "description": _evaluation_description(
                    operator,
                    request.ideal,
                    ideal_evaluation,
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "title": request.title,
        "roof_description": (
            f"Ideal roof {request.ideal.label}: peak compute = "
            f"{_format_si(request.ideal.compute, 'FLOP/s')}, bandwidth = "
            f"{_format_si(request.ideal.bandwidth, 'Byte/s')}, ridge point = "
            f"{_format_si(request.ideal.ridge_point, 'FLOP/Byte')}"
        ),
        "roofs": {key: _roof_to_dict(roof) for key, roof in named_roofs},
        "operators": operators,
    }
