from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .model import _OPERATOR_COLORS, OperatorPoint, PlotRequest, RoofSpec, build_analysis
from .units import parse_arithmetic_intensity, parse_bandwidth, parse_compute

_MAX_OPERATORS = 256
_PLOT_FORMATS = {".pdf", ".png", ".svg"}
_ROOT_KEYS = {"title", "output", "plot", "ideal", "actual", "operators"}
_PLOT_KEYS = {"width", "height", "show_bound_regions"}
_ROOF_KEYS = {
    "label",
    "compute",
    "bandwidth",
    "color",
    "precision",
    "compute_kind",
    "bandwidth_level",
    "bandwidth_kind",
    "fma_flop_count",
    "sparsity",
    "notes",
}
_OPERATOR_KEYS = {"name", "label", "compute", "arithmetic_intensity", "color"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a roofline plot.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", help="Path to a strict JSON config file.")
    parser.add_argument("--title", help="Plot title.")
    parser.add_argument(
        "--output",
        help=(
            "Output path. Plot mode supports SVG, PNG, or PDF; analysis-only "
            "mode requires JSON. Defaults: roofline.svg or analysis.json."
        ),
    )
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
        metavar=("NAME", "COMPUTE", "ARITHMETIC_INTENSITY"),
        help=(
            "Operator point as name, compute, and arithmetic intensity. "
            "Repeatable. CLI operators replace (rather than append to) configured "
            "operators. Quote values containing spaces."
        ),
    )
    parser.add_argument(
        "--analysis-only",
        "--silent",
        dest="analysis_only",
        action="store_true",
        help=(
            "Skip image generation and atomically write JSON analysis. "
            "--silent remains as a compatibility alias."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        request, output_path = load_request_from_args(args)
        analysis = build_analysis(request)
        analysis_json = json.dumps(
            analysis,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )

        output_file = Path(output_path)
        if args.analysis_only:
            _atomic_write_text(output_file, analysis_json + "\n")
            print(analysis_json)
            print(f"Wrote analysis to {output_file}", file=sys.stderr, flush=True)
            return 0

        from .plot import write_plot

        _atomic_write_plot(request, output_file, write_plot)
        print(analysis_json)
        print(f"Wrote roofline plot to {output_file}", file=sys.stderr, flush=True)
        return 0
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))


def load_request_from_args(args: argparse.Namespace) -> tuple[PlotRequest, str]:
    config = _load_config(args.config) if args.config else {}
    _validate_config(config)
    analysis_only = bool(getattr(args, "analysis_only", getattr(args, "silent", False)))

    title = args.title if args.title is not None else config.get("title", "roofp")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")

    output = _resolve_output(args.output, config.get("output"), analysis_only)

    plot_config = config.get("plot", {})
    if not isinstance(plot_config, dict):
        raise ValueError("plot must be a JSON object")
    width = args.width if args.width is not None else plot_config.get("width", 1280)
    height = args.height if args.height is not None else plot_config.get("height", 720)
    show_bound_regions = plot_config.get("show_bound_regions", True)
    if not isinstance(show_bound_regions, bool):
        raise ValueError("plot.show_bound_regions must be a boolean")

    ideal_config = config.get("ideal", {})
    if not isinstance(ideal_config, dict):
        raise ValueError("ideal must be a JSON object")
    ideal = _build_roof(
        config=ideal_config,
        default_label="Ideal roof",
        default_color="#0072B2",
        compute_override=args.ideal_compute,
        bandwidth_override=args.ideal_bandwidth,
    )

    actual_config = config.get("actual", {})
    if not isinstance(actual_config, dict):
        raise ValueError("actual must be a JSON object")
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
            config=actual_config,
            default_label="Measured roof",
            default_color="#D55E00",
            compute_override=actual_compute,
            bandwidth_override=actual_bandwidth,
        )

    config_operators = config.get("operators", [])
    if not isinstance(config_operators, list):
        raise ValueError("operators must be a JSON array")
    if len(config_operators) > _MAX_OPERATORS:
        raise ValueError(f"operators supports at most {_MAX_OPERATORS} entries")
    if args.operator and len(args.operator) > _MAX_OPERATORS:
        raise ValueError(f"--operator supports at most {_MAX_OPERATORS} entries")

    operators = (
        tuple(
            _operator_from_cli(item, _OPERATOR_COLORS[i % len(_OPERATOR_COLORS)])
            for i, item in enumerate(args.operator)
        )
        if args.operator
        else tuple(
            _operator_from_mapping(
                item,
                _OPERATOR_COLORS[i % len(_OPERATOR_COLORS)],
            )
            for i, item in enumerate(config_operators)
        )
    )

    return (
        PlotRequest(
            title=title,
            ideal=ideal,
            actual=actual,
            operators=operators,
            width=width,
            height=height,
            show_bound_regions=show_bound_regions,
        ),
        output,
    )


def _resolve_output(
    cli_output: str | None,
    configured_output: Any,
    analysis_only: bool,
) -> str:
    if cli_output is not None:
        output = cli_output
    elif configured_output is not None:
        if not isinstance(configured_output, str) or not configured_output.strip():
            raise ValueError("output must be a non-empty path string")
        # A plot-oriented config should remain usable with the mode-switching
        # --analysis-only flag without writing JSON into an image path.
        if analysis_only and Path(configured_output).suffix.lower() != ".json":
            output = "analysis.json"
        else:
            output = configured_output
    else:
        output = "analysis.json" if analysis_only else "roofline.svg"

    if not isinstance(output, str) or not output.strip():
        raise ValueError("output must be a non-empty path string")
    suffix = Path(output).suffix.lower()
    if analysis_only and suffix != ".json":
        raise ValueError("analysis-only output must use the .json extension")
    if not analysis_only and suffix not in _PLOT_FORMATS:
        supported = ", ".join(sorted(_PLOT_FORMATS))
        raise ValueError(f"plot output must use one of: {supported}")
    return output


def _load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Config root must be a JSON object")
    return data


def _reject_unknown_keys(value: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Unknown {path} field(s): {', '.join(unknown)}")


def _validate_config(config: dict[str, Any]) -> None:
    _reject_unknown_keys(config, _ROOT_KEYS, "config")
    plot = config.get("plot", {})
    if isinstance(plot, dict):
        _reject_unknown_keys(plot, _PLOT_KEYS, "plot")
    for field_name in ("ideal", "actual"):
        roof = config.get(field_name, {})
        if isinstance(roof, dict):
            _reject_unknown_keys(roof, _ROOF_KEYS, field_name)
    operators = config.get("operators", [])
    if isinstance(operators, list):
        for index, operator in enumerate(operators):
            if isinstance(operator, dict):
                _reject_unknown_keys(
                    operator,
                    _OPERATOR_KEYS,
                    f"operators[{index}]",
                )


def _build_roof(
    *,
    config: dict[str, Any],
    default_label: str,
    default_color: str,
    compute_override: Any,
    bandwidth_override: Any,
) -> RoofSpec:
    label = config.get("label", default_label)
    compute = compute_override if compute_override is not None else config.get("compute")
    bandwidth = bandwidth_override if bandwidth_override is not None else config.get("bandwidth")
    if compute is None or bandwidth is None:
        raise ValueError(
            f"{label} requires both compute and bandwidth. "
            "Provide them in JSON config or CLI arguments."
        )
    return RoofSpec(
        label=label,
        compute=parse_compute(compute),
        bandwidth=parse_bandwidth(bandwidth),
        color=config.get("color", default_color),
        precision=config.get("precision"),
        compute_kind=config.get("compute_kind", "unspecified"),
        bandwidth_level=config.get("bandwidth_level", "unspecified"),
        bandwidth_kind=config.get("bandwidth_kind", "unspecified"),
        fma_flop_count=config.get("fma_flop_count"),
        sparsity=config.get("sparsity"),
        notes=config.get("notes"),
    )


def _operator_from_cli(values: list[str], color: str) -> OperatorPoint:
    name, compute, arithmetic_intensity = values
    return OperatorPoint(
        name=name,
        compute=parse_compute(compute),
        arithmetic_intensity=parse_arithmetic_intensity(arithmetic_intensity),
        color=color,
    )


def _operator_from_mapping(item: dict[str, Any], auto_color: str) -> OperatorPoint:
    if not isinstance(item, dict):
        raise ValueError("Each operator entry must be a JSON object")
    name = item.get("name") or item.get("label")
    if not name:
        raise ValueError("Each operator entry requires a name")
    if "compute" not in item:
        raise ValueError(f"Operator {name!r} requires compute")
    if "arithmetic_intensity" not in item:
        raise ValueError(f"Operator {name!r} requires arithmetic_intensity")
    return OperatorPoint(
        name=name,
        compute=parse_compute(item["compute"]),
        arithmetic_intensity=parse_arithmetic_intensity(item["arithmetic_intensity"]),
        color=item.get("color", auto_color),
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _atomic_write_plot(request: PlotRequest, path: Path, renderer) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=path.suffix,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
        renderer(request, str(temporary_path))
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
