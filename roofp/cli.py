from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import OperatorPoint, PlotRequest, RoofSpec, _OPERATOR_COLORS, build_analysis
from .plot import write_plot
from .units import parse_bandwidth, parse_compute


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a roofline plot.")
    parser.add_argument("--config", help="Path to a JSON config file.")
    parser.add_argument("--title", help="Plot title.")
    parser.add_argument("--output", help="Output path: image (default) or JSON analysis with --silent. Default: roofline.svg.")
    parser.add_argument("--width", type=int, help="Canvas width.")
    parser.add_argument("--height", type=int, help="Canvas height.")

    parser.add_argument(
        "--ideal-compute",
        help='Ideal peak compute, for example "1.2 TFLOP/s" or 1.2e12.',
    )
    parser.add_argument(
        "--ideal-bandwidth",
        help='Ideal peak bandwidth, for example "800 GB/s" or 8.0e11.',
    )
    parser.add_argument(
        "--actual-compute",
        help='Measured peak compute, for example "800 GFLOP/s".',
    )
    parser.add_argument(
        "--actual-bandwidth",
        help='Measured peak bandwidth, for example "500 GB/s".',
    )
    parser.add_argument(
        "--operator",
        nargs=3,
        action="append",
        metavar=("NAME", "COMPUTE", "BANDWIDTH"),
        help='Operator point as: name compute bandwidth. Repeatable. Quote values with spaces, for example --operator GEMM "650 GFLOP/s" "200 GB/s".',
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Output machine-readable JSON analysis only, skip image generation.",
    )
    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    request, output_path = load_request_from_args(args)

    analysis = build_analysis(request)
    analysis_json = json.dumps(analysis, indent=2)

    if args.silent:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(analysis_json, encoding="utf-8")
        print(f"Wrote analysis to {output_file}", flush=True)
        return 0

    print(analysis_json)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_plot(request, str(output_file))
    print(f"Wrote roofline plot to {output_file}", flush=True)
    return 0


def load_request_from_args(args: argparse.Namespace) -> tuple[PlotRequest, str]:
    config = _load_config(args.config) if args.config else {}

    title = args.title or config.get("title", "roofp")
    output = args.output or config.get("output", "roofline.svg")
    plot_config = config.get("plot", {})
    width = args.width or plot_config.get("width", 1280)
    height = args.height or plot_config.get("height", 720)

    ideal_config = config.get("ideal", {})
    ideal = _build_roof(
        default_label=ideal_config.get("label", "Ideal roof"),
        color="#2563eb",
        compute=args.ideal_compute
        if args.ideal_compute is not None
        else ideal_config.get("compute"),
        bandwidth=args.ideal_bandwidth
        if args.ideal_bandwidth is not None
        else ideal_config.get("bandwidth"),
    )

    actual_config = config.get("actual", {})
    actual_compute = (
        args.actual_compute if args.actual_compute is not None else actual_config.get("compute")
    )
    actual_bandwidth = (
        args.actual_bandwidth
        if args.actual_bandwidth is not None
        else actual_config.get("bandwidth")
    )
    actual = None
    if actual_compute is not None or actual_bandwidth is not None:
        actual = _build_roof(
            default_label=actual_config.get("label", "Measured roof"),
            color="#dc2626",
            compute=actual_compute,
            bandwidth=actual_bandwidth,
        )

    operators = (
        [
            _operator_from_cli(
                item, _OPERATOR_COLORS[i % len(_OPERATOR_COLORS)]
            )
            for i, item in enumerate(args.operator)
        ]
        if args.operator
        else [
            _operator_from_mapping(
                item, _OPERATOR_COLORS[i % len(_OPERATOR_COLORS)]
            )
            for i, item in enumerate(config.get("operators", []))
        ]
    )

    return (
        PlotRequest(
            title=title,
            ideal=ideal,
            actual=actual,
            operators=operators,
            width=width,
            height=height,
        ),
        output,
    )


def _load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Config root must be a JSON object")
    return data


def _build_roof(default_label: str, color: str, compute, bandwidth) -> RoofSpec:
    if compute is None or bandwidth is None:
        raise ValueError(
            f"{default_label} requires both compute and bandwidth. "
            "Provide them in JSON config or CLI arguments."
        )
    return RoofSpec(
        label=default_label,
        compute=parse_compute(compute),
        bandwidth=parse_bandwidth(bandwidth),
        color=color,
    )


def _operator_from_cli(values: list[str], color: str) -> OperatorPoint:
    name, compute, bandwidth = values
    return OperatorPoint(
        name=name,
        compute=parse_compute(compute),
        bandwidth=parse_bandwidth(bandwidth),
        color=color,
    )


def _operator_from_mapping(item: dict, auto_color: str) -> OperatorPoint:
    if not isinstance(item, dict):
        raise ValueError("Each operator entry must be a JSON object")
    name = item.get("name") or item.get("label")
    if not name:
        raise ValueError("Each operator entry requires a name")
    return OperatorPoint(
        name=str(name),
        compute=parse_compute(item["compute"]),
        bandwidth=parse_bandwidth(item["bandwidth"]),
        color=str(item.get("color", auto_color)),
    )
