"""Structured MCP tools for roofline analysis."""

from __future__ import annotations

import io
import logging
import math
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .model import (
    RELATIVE_TOLERANCE,
    SCHEMA_VERSION,
    BandwidthKind,
    BandwidthLevel,
    ComputeKind,
    OperatorPoint,
    PlotRequest,
    RoofSpec,
    build_analysis,
    classify_bound,
    comparison_metadata_warnings,
)
from .units import parse_arithmetic_intensity, parse_bandwidth, parse_compute

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="roofp",
    instructions=(
        "Schema-versioned Roofline analysis with structured inputs and outputs. "
        "Use theoretical workload comparison separately from per-hardware measurements."
    ),
)

_MAX_ROOFS = 32
_MAX_OPERATORS = 256
_MAX_PLOT_POINTS = 64
_OPERATOR_COLORS = [
    "#7c3aed",
    "#059669",
    "#d97706",
    "#db2777",
    "#0891b2",
    "#65a30d",
]
_ROOF_COLORS = [
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#E69F00",
    "#CC79A7",
    "#56B4E9",
]

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]
UnitText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
UnitValue = UnitText | int | float


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoofInput(StrictModel):
    """One hardware roof and the conventions used to measure it."""

    label: ShortText
    compute: UnitValue
    bandwidth: UnitValue
    color: ShortText | None = None
    precision: ShortText | None = None
    compute_kind: ComputeKind = "unspecified"
    bandwidth_level: BandwidthLevel = "unspecified"
    bandwidth_kind: BandwidthKind = "unspecified"
    fma_flop_count: Literal[1, 2] | None = None
    sparsity: ShortText | None = None
    notes: ShortText | None = None

    def to_spec(self, default_color: str) -> RoofSpec:
        return RoofSpec(
            label=self.label,
            compute=parse_compute(self.compute),
            bandwidth=parse_bandwidth(self.bandwidth),
            color=self.color or default_color,
            precision=self.precision,
            compute_kind=self.compute_kind,
            bandwidth_level=self.bandwidth_level,
            bandwidth_kind=self.bandwidth_kind,
            fma_flop_count=self.fma_flop_count,
            sparsity=self.sparsity,
            notes=self.notes,
        )


class OperatorInput(StrictModel):
    """A measured operator point."""

    name: ShortText
    compute: UnitValue
    arithmetic_intensity: UnitValue
    color: ShortText | None = None

    def to_point(self, default_color: str) -> OperatorPoint:
        return OperatorPoint(
            name=self.name,
            compute=parse_compute(self.compute),
            arithmetic_intensity=parse_arithmetic_intensity(self.arithmetic_intensity),
            color=self.color or default_color,
        )


class HardwareMeasurement(StrictModel):
    """Measured workload performance on one named roof."""

    roof_label: ShortText
    compute: UnitValue


class WorkloadInput(StrictModel):
    """A workload used for theoretical and optional measured comparison."""

    name: ShortText
    arithmetic_intensity: UnitValue
    measurements: Annotated[list[HardwareMeasurement], Field(max_length=_MAX_ROOFS)] = Field(
        default_factory=list
    )


class AnalysisResult(StrictModel):
    schema_version: str
    title: str
    roof_description: str
    roofs: dict[str, dict[str, Any]]
    operators: list[dict[str, Any]]


class GenerateRooflineResult(StrictModel):
    schema_version: str
    analysis: AnalysisResult
    svg: str | None = None


class CompareRooflinesResult(StrictModel):
    schema_version: str
    comparison_matrix: list[dict[str, Any]]
    metadata_warnings: list[str]
    summary: list[str]
    svg: str | None = None


def _make_operators(inputs: list[OperatorInput]) -> tuple[OperatorPoint, ...]:
    return tuple(
        item.to_point(_OPERATOR_COLORS[index % len(_OPERATOR_COLORS)])
        for index, item in enumerate(inputs)
    )


def _svg_to_string(request: PlotRequest) -> str:
    from .plot import write_plot

    buffer = io.BytesIO()
    write_plot(request, buffer)
    return buffer.getvalue().decode("utf-8")


def _validate_plot_size(item_count: int, include_svg: bool) -> None:
    if include_svg and item_count > _MAX_PLOT_POINTS:
        raise ValueError(
            f"SVG output supports at most {_MAX_PLOT_POINTS} plotted points; "
            "set include_svg=false to analyze larger inputs"
        )


def _validate_item_count(
    name: str,
    item_count: int,
    *,
    maximum: int,
    minimum: int = 0,
) -> None:
    if item_count < minimum:
        raise ValueError(f"{name} requires at least {minimum} item(s)")
    if item_count > maximum:
        raise ValueError(f"{name} supports at most {maximum} item(s)")


@mcp.tool(
    structured_output=True,
    description=(
        "Analyze one required ideal hardware roof, an optional measured roof, and "
        "structured operator points. Set include_svg=true to include an SVG; it is "
        "off by default to keep MCP responses compact."
    ),
)
def generate_roofline(
    ideal: RoofInput,
    operators: Annotated[
        list[OperatorInput],
        Field(max_length=_MAX_OPERATORS),
    ]
    | None = None,
    actual: RoofInput | None = None,
    title: ShortText = "roofp",
    include_svg: bool = False,
) -> GenerateRooflineResult:
    """Generate schema-versioned analysis and optionally an SVG plot."""
    operators = operators or []
    _validate_item_count("operators", len(operators), maximum=_MAX_OPERATORS)
    _validate_plot_size(len(operators), include_svg)
    ideal_spec = ideal.to_spec(_ROOF_COLORS[0])
    actual_spec = actual.to_spec(_ROOF_COLORS[1]) if actual is not None else None
    points = _make_operators(operators)
    request = PlotRequest(
        title=title,
        ideal=ideal_spec,
        actual=actual_spec,
        operators=points,
    )
    logger.info(
        "generate_roofline operators=%d actual=%s svg=%s",
        len(points),
        actual_spec is not None,
        include_svg,
    )
    analysis = AnalysisResult.model_validate(build_analysis(request))
    return GenerateRooflineResult(
        schema_version=SCHEMA_VERSION,
        analysis=analysis,
        svg=_svg_to_string(request) if include_svg else None,
    )


@mcp.tool(
    structured_output=True,
    description=(
        "Analyze structured measured operator points against one hardware roof. "
        "Returns per-roof bound, ceiling, utilization, headroom, and above-roof state."
    ),
)
def analyze_performance(
    roof: RoofInput,
    operators: Annotated[list[OperatorInput], Field(max_length=_MAX_OPERATORS)],
    title: ShortText = "roofp analysis",
) -> AnalysisResult:
    """Analyze measured points without rendering a plot."""
    _validate_item_count("operators", len(operators), maximum=_MAX_OPERATORS)
    request = PlotRequest(
        title=title,
        ideal=roof.to_spec(_ROOF_COLORS[0]),
        operators=_make_operators(operators),
    )
    logger.info("analyze_performance operators=%d", len(operators))
    return AnalysisResult.model_validate(build_analysis(request))


@mcp.tool(
    structured_output=True,
    description=(
        "Compare theoretical ceilings for workloads across two or more peer roofs. "
        "Optional per-hardware measurements enable valid utilization rankings; "
        "above-roof measurements are reported but excluded from that ranking."
    ),
)
def compare_rooflines(
    roofs: Annotated[
        list[RoofInput],
        Field(min_length=2, max_length=_MAX_ROOFS),
    ],
    workloads: Annotated[
        list[WorkloadInput],
        Field(max_length=_MAX_OPERATORS),
    ]
    | None = None,
    title: ShortText = "Roofline Comparison",
    include_svg: bool = False,
) -> CompareRooflinesResult:
    """Compare peer roofs without conflating theory and measurements."""
    workloads = workloads or []
    _validate_item_count("roofs", len(roofs), minimum=2, maximum=_MAX_ROOFS)
    _validate_item_count("workloads", len(workloads), maximum=_MAX_OPERATORS)
    _validate_plot_size(
        sum(len(workload.measurements) for workload in workloads),
        include_svg,
    )
    specs = tuple(
        roof.to_spec(_ROOF_COLORS[index % len(_ROOF_COLORS)]) for index, roof in enumerate(roofs)
    )
    labels = [roof.label for roof in specs]
    if len(labels) != len(set(labels)):
        duplicates = sorted({label for label in labels if labels.count(label) > 1})
        raise ValueError(f"Roof labels must be unique: {', '.join(duplicates)}")

    comparison: list[dict[str, Any]] = []
    plot_points: list[OperatorPoint] = []
    summary: list[str] = []
    for workload in workloads:
        intensity = parse_arithmetic_intensity(workload.arithmetic_intensity)
        measurements: dict[str, float] = {}
        for measurement in workload.measurements:
            if measurement.roof_label not in labels:
                raise ValueError(
                    f"Workload {workload.name!r} references unknown roof {measurement.roof_label!r}"
                )
            if measurement.roof_label in measurements:
                raise ValueError(
                    f"Workload {workload.name!r} has duplicate measurement for "
                    f"{measurement.roof_label!r}"
                )
            measurements[measurement.roof_label] = parse_compute(measurement.compute)

        hardware: dict[str, dict[str, Any]] = {}
        best_ceiling_label: str | None = None
        best_ceiling = -math.inf
        valid_utilizations: list[tuple[float, str]] = []
        excluded_above_roof: list[str] = []
        bounds: set[str] = set()

        for roof in specs:
            ceiling = min(roof.compute, roof.bandwidth * intensity)
            bound = classify_bound(intensity, roof.ridge_point)
            bounds.add(bound)
            result: dict[str, Any] = {
                "bound": bound,
                "ridge_ratio": intensity / roof.ridge_point,
                "theoretical_ceiling_flop_per_second": ceiling,
                "measured_performance_flop_per_second": None,
                "utilization_ratio": None,
                "remaining_headroom_ratio": None,
                "above_roof": None,
            }
            if ceiling > best_ceiling:
                best_ceiling = ceiling
                best_ceiling_label = roof.label

            measured = measurements.get(roof.label)
            if measured is not None:
                utilization = measured / ceiling
                at_roof = math.isclose(
                    utilization,
                    1.0,
                    rel_tol=RELATIVE_TOLERANCE,
                    abs_tol=0.0,
                )
                above_roof = utilization > 1.0 and not at_roof
                result.update(
                    {
                        "measured_performance_flop_per_second": measured,
                        "utilization_ratio": utilization,
                        "remaining_headroom_ratio": (0.0 if at_roof else 1.0 - utilization),
                        "above_roof": above_roof,
                    }
                )
                if above_roof:
                    excluded_above_roof.append(roof.label)
                else:
                    valid_utilizations.append((utilization, roof.label))
                plot_points.append(
                    OperatorPoint(
                        name=f"{workload.name} @ {roof.label}",
                        compute=measured,
                        arithmetic_intensity=intensity,
                        color=roof.color,
                    )
                )
            hardware[roof.label] = result

        assert best_ceiling_label is not None
        best_utilization_label = None
        best_utilization = None
        if valid_utilizations:
            best_utilization, best_utilization_label = max(valid_utilizations)
        bottleneck_shift = len(bounds) > 1
        entry = {
            "workload": workload.name,
            "arithmetic_intensity_flop_per_byte": intensity,
            "hardware": hardware,
            "best_theoretical_hardware": best_ceiling_label,
            "best_theoretical_ceiling_flop_per_second": best_ceiling,
            "best_valid_utilization_hardware": best_utilization_label,
            "best_valid_utilization_ratio": best_utilization,
            "excluded_above_roof_measurements": excluded_above_roof,
            "bottleneck_shift": bottleneck_shift,
        }
        comparison.append(entry)

        shift_text = (
            "; ".join(f"{hardware[roof.label]['bound']}-bound on {roof.label}" for roof in specs)
            if bottleneck_shift
            else "same bound across all hardware"
        )
        measured_text = (
            f" Best valid utilization: {best_utilization:.1%} on {best_utilization_label}."
            if best_utilization_label is not None and best_utilization is not None
            else " No valid per-hardware utilization ranking is available."
        )
        excluded_text = (
            " Above-roof measurements excluded: " + ", ".join(excluded_above_roof) + "."
            if excluded_above_roof
            else ""
        )
        summary.append(
            f"{workload.name}: {shift_text}. Highest theoretical ceiling on "
            f"{best_ceiling_label} ({best_ceiling:.3g} FLOP/s)."
            f"{measured_text}{excluded_text}"
        )

    request = PlotRequest(
        title=title,
        ideal=specs[0],
        additional_roofs=specs[1:],
        operators=tuple(plot_points),
        show_bound_regions=False,
        peer_roofs=True,
    )
    logger.info(
        "compare_rooflines roofs=%d workloads=%d measurements=%d svg=%s",
        len(specs),
        len(workloads),
        len(plot_points),
        include_svg,
    )
    return CompareRooflinesResult(
        schema_version=SCHEMA_VERSION,
        comparison_matrix=comparison,
        metadata_warnings=comparison_metadata_warnings(specs),
        summary=summary,
        svg=_svg_to_string(request) if include_svg else None,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
