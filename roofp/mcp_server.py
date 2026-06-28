"""roofp MCP server — roofline analysis tools for AI agents."""

from __future__ import annotations

import io
import json
import math
from typing import Any

from mcp.server.fastmcp import FastMCP

from .model import OperatorPoint, PlotRequest, RoofSpec, build_analysis
from .plot import write_plot
from .units import parse_arithmetic_intensity, parse_bandwidth, parse_compute
mcp = FastMCP(
    name="roofp",
    instructions="Roofline performance analysis: generate plots, analyze operator bounds, compare hardware.",
)


def _make_roof(label: str, compute: str, bandwidth: str, color: str = "#2563eb") -> RoofSpec:
    return RoofSpec(
        label=label,
        compute=parse_compute(compute),
        bandwidth=parse_bandwidth(bandwidth),
        color=color,
    )


def _make_operator(name: str, compute: str, arithmetic_intensity: str, color: str = "#1f2937") -> OperatorPoint:
    compute_val = parse_compute(compute)
    ai_val = parse_arithmetic_intensity(arithmetic_intensity)
    return OperatorPoint(
        name=name,
        compute=compute_val,
        bandwidth=compute_val / ai_val,
        color=color,
    )


def _svg_to_string(request: PlotRequest) -> str:
    """Generate SVG and return as string."""
    buf = io.BytesIO()
    write_plot(request, buf)
    return buf.getvalue().decode("utf-8")


# ── tools ──────────────────────────────────────────────────────────


@mcp.tool(
    description="Generate a roofline plot (SVG) and analysis JSON for a single hardware configuration. Ideal roof is required; actual roof and operators are optional.",
)
def generate_roofline(
    ideal_label: str = "Ideal roof",
    ideal_compute: str = "",
    ideal_bandwidth: str = "",
    actual_label: str = "",
    actual_compute: str = "",
    actual_bandwidth: str = "",
    operators_json: str = "[]",
    title: str = "roofp",
) -> str:
    """Generate a roofline plot and return analysis JSON + SVG base64."""
    if not ideal_compute or not ideal_bandwidth:
        return json.dumps({"error": "ideal_compute and ideal_bandwidth are required"})

    ideal = _make_roof(ideal_label, ideal_compute, ideal_bandwidth, "#2563eb")

    actual = None
    if actual_compute and actual_bandwidth:
        actual = _make_roof(actual_label or "Measured roof", actual_compute, actual_bandwidth, "#dc2626")

    operators: list[OperatorPoint] = []
    try:
        op_data = json.loads(operators_json)
    except json.JSONDecodeError:
        return json.dumps({"error": f"Invalid operators_json: {operators_json!r}"})

    _OP_COLORS = ["#7c3aed", "#059669", "#d97706", "#db2777", "#0891b2", "#65a30d"]
    for i, item in enumerate(op_data):
        if not isinstance(item, dict):
            return json.dumps({"error": f"Each operator must be an object, got {item!r}"})
        name = item.get("name") or item.get("label") or f"op_{i}"
        compute = item.get("compute", "")
        ai = item.get("arithmetic_intensity", "")
        if not compute or not ai:
            return json.dumps({"error": f"Operator {name!r} requires compute and arithmetic_intensity"})
        operators.append(_make_operator(name, compute, ai, item.get("color", _OP_COLORS[i % len(_OP_COLORS)])))

    request = PlotRequest(title=title, ideal=ideal, actual=actual, operators=operators)
    analysis = build_analysis(request)
    svg_text = _svg_to_string(request)

    return json.dumps({"analysis": analysis, "svg": svg_text}, indent=2)


@mcp.tool(
    description="Analyze operator performance against a roofline: determine bound type, headroom, ridge ratio, and return a human-readable description. No plot generated.",
)
def analyze_performance(
    ideal_compute: str,
    ideal_bandwidth: str,
    operators_json: str,
) -> str:
    """Quick performance analysis without generating a plot."""
    if not ideal_compute or not ideal_bandwidth:
        return json.dumps({"error": "ideal_compute and ideal_bandwidth are required"})

    roof = _make_roof("Ideal", ideal_compute, ideal_bandwidth)
    try:
        op_data = json.loads(operators_json)
    except json.JSONDecodeError:
        return json.dumps({"error": f"Invalid operators_json: {operators_json!r}"})

    operators: list[OperatorPoint] = []
    for i, item in enumerate(op_data):
        if not isinstance(item, dict):
            return json.dumps({"error": f"Each operator must be an object"})
        name = item.get("name", f"op_{i}")
        operators.append(_make_operator(name, item.get("compute", ""), item.get("arithmetic_intensity", "")))

    request = PlotRequest(title="roofp", ideal=roof, operators=operators)
    return json.dumps(build_analysis(request), indent=2)


@mcp.tool(
    description="Compare operator performance across multiple hardware configurations. Returns a comparison matrix, best-hardware recommendation, bottleneck analysis, and SVG overlay plot.",
)
def compare_rooflines(
    roofs_json: str,
    operators_json: str = "[]",
    title: str = "Roofline Comparison",
) -> str:
    """Compare multiple roofs against the same operators."""
    try:
        roof_data = json.loads(roofs_json)
    except json.JSONDecodeError:
        return json.dumps({"error": f"Invalid roofs_json: {roofs_json!r}"})

    _ROOF_COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#db2777"]
    roofs: list[RoofSpec] = []
    for i, item in enumerate(roof_data):
        if not isinstance(item, dict):
            return json.dumps({"error": f"Each roof must be an object"})
        roofs.append(_make_roof(
            label=item.get("label", f"Roof_{i}"),
            compute=item.get("compute", ""),
            bandwidth=item.get("bandwidth", ""),
            color=item.get("color", _ROOF_COLORS[i % len(_ROOF_COLORS)]),
        ))

    try:
        op_data = json.loads(operators_json)
    except json.JSONDecodeError:
        return json.dumps({"error": f"Invalid operators_json: {operators_json!r}"})

    _OP_COLORS = ["#1f2937", "#4b5563", "#9ca3af"]
    operators: list[OperatorPoint] = []
    for i, item in enumerate(op_data):
        if not isinstance(item, dict):
            return json.dumps({"error": f"Each operator must be an object"})
        name = item.get("name", f"op_{i}")
        operators.append(_make_operator(
            name,
            item.get("compute", ""),
            item.get("arithmetic_intensity", ""),
            _OP_COLORS[i % len(_OP_COLORS)],
        ))

    # Build comparison matrix
    primary = roofs[0]
    comparison: list[dict[str, Any]] = []
    for op in operators:
        ai = op.arithmetic_intensity
        hw_results: dict[str, dict] = {}
        best_hw = None
        best_headroom = -1.0
        bounds: set[str] = set()

        for roof in roofs:
            ridge = roof.ridge_point
            roof_perf = min(roof.compute, roof.bandwidth * ai)
            headroom = op.compute / roof_perf if roof_perf else None

            if ai < ridge:
                bound = "memory"
            elif ai > ridge:
                bound = "compute"
            else:
                bound = "ridge"

            hw_results[roof.label] = {
                "bound": bound,
                "ridge_ratio": round(ai / ridge, 4),
                "headroom_ratio": round(headroom, 4) if headroom else None,
                "roof_performance_flops": roof_perf,
            }
            bounds.add(bound)

            if headroom and headroom > best_headroom:
                best_headroom = headroom
                best_hw = roof.label

        bottleneck_shift = None
        if len(bounds) > 1:
            bound_strs = [f"{hw_results[r.label]['bound']}-bound on {r.label}" for r in roofs]
            bottleneck_shift = "; ".join(bound_strs)

        comparison.append({
            "operator": op.name,
            "arithmetic_intensity_flop_per_byte": ai,
            "compute_flops": op.compute,
            "hardware": hw_results,
            "best_hardware": best_hw,
            "best_headroom": round(best_headroom, 4),
            "bottleneck_shift": bottleneck_shift,
        })

    # Generate overlay plot: each roof becomes a dashed line with its own color
    request = PlotRequest(title=title, ideal=primary, operators=operators)
    svg_text = _svg_to_string(request)

    summary_parts: list[str] = []
    for entry in comparison:
        if entry["bottleneck_shift"]:
            summary_parts.append(f"{entry['operator']}: {entry['bottleneck_shift']}. Best on {entry['best_hardware']} (headroom {entry['best_headroom']:.2%}).")
        else:
            summary_parts.append(f"{entry['operator']}: same bound across all hardware. Best on {entry['best_hardware']} (headroom {entry['best_headroom']:.2%}).")

    return json.dumps({
        "comparison_matrix": comparison,
        "summary": summary_parts,
        "svg": svg_text,
    }, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
