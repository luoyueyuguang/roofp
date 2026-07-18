from __future__ import annotations

import io
import math
import os
import tempfile
import threading
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "roofp-matplotlib"))

import matplotlib
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from .model import PlotRequest, RoofSpec

_PLOT_LOCK = threading.RLock()
_SUPPORTED_OUTPUT_FORMATS = {"pdf", "png", "svg"}


def write_plot(request: PlotRequest, output_path: str | io.BytesIO) -> None:
    """Render a request, inferring file format from paths and using SVG for buffers."""
    with _PLOT_LOCK:
        _write_plot(request, output_path)


def _write_plot(request: PlotRequest, output_path: str | io.BytesIO) -> None:
    if isinstance(output_path, io.BytesIO):
        target: str | io.BytesIO = output_path
        output_format = "svg"
    else:
        path = Path(output_path)
        output_format = path.suffix.lower().lstrip(".")
        if output_format not in _SUPPORTED_OUTPUT_FORMATS:
            supported = ", ".join(sorted(_SUPPORTED_OUTPUT_FORMATS))
            raise ValueError(
                f"Unsupported output format {path.suffix or '<none>'!r}. "
                f"Supported formats: {supported}."
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        target = str(path)

    fig = Figure(
        figsize=(request.width / 100, request.height / 100),
        dpi=100,
    )
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(1, 1, 1)
    try:
        x_min, x_max, y_min, y_max = _axis_bounds(request)
        x_values = np.logspace(math.log10(x_min), math.log10(x_max), 512)

        for index, roof in enumerate(request.roofs):
            # Peer roofs are equally ranked alternatives. For a single target,
            # dashed lines distinguish measured/additional roofs from the ideal.
            dashed = not request.peer_roofs and index > 0
            _plot_roof(
                ax,
                roof,
                x_values,
                dashed=dashed,
                show_ridge_line=request.peer_roofs,
                y_min=y_min,
            )

        if request.show_bound_regions and not request.peer_roofs:
            _fill_regions(ax, request.ideal, x_min, x_max, y_min)

        for operator in request.operators:
            ai = operator.arithmetic_intensity
            perf = operator.compute
            ax.scatter(
                ai,
                perf,
                s=58,
                color=operator.color,
                edgecolor="white",
                linewidth=0.9,
                zorder=4,
            )
            ax.annotate(
                operator.name,
                (ai, perf),
                textcoords="offset points",
                xytext=(7, 7),
                fontsize=9,
                color=operator.color,
            )
            # drop lines to axes
            ax.plot(
                [ai, ai],
                [y_min, perf],
                color="#374151",
                linestyle="--",
                linewidth=1.1,
                alpha=0.75,
                zorder=2,
            )
            ax.plot(
                [x_min, ai],
                [perf, perf],
                color="#374151",
                linestyle="--",
                linewidth=1.1,
                alpha=0.75,
                zorder=2,
            )
            # coordinate labels on axes
            ax.annotate(
                _format_engineering(ai),
                xy=(ai, 0),
                xycoords=("data", "axes fraction"),
                xytext=(0, -14),
                textcoords="offset points",
                fontsize=7,
                color=operator.color,
                ha="center",
                va="top",
            )
            ax.annotate(
                _format_engineering(perf),
                xy=(0, perf),
                xycoords=("axes fraction", "data"),
                xytext=(-4, 0),
                textcoords="offset points",
                fontsize=7,
                color=operator.color,
                ha="right",
                va="center",
            )

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.set_title(request.title, fontsize=15, pad=14)
        ax.set_xlabel("Arithmetic Intensity (FLOP/Byte)")
        ax.set_ylabel("Attainable Performance (FLOP/s)")
        ax.grid(True, which="major", color="#d1d5db", linewidth=0.8)
        ax.grid(True, which="minor", color="#e5e7eb", linewidth=0.45, alpha=0.7)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: _format_engineering(value)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _format_engineering(value)))
        ax.legend(loc="lower right", frameon=True)

        fig.tight_layout()
        if output_format == "svg":
            # Keep text as text instead of large glyph paths. This materially
            # reduces MCP response size and keeps generated SVGs searchable.
            with matplotlib.rc_context({"svg.fonttype": "none"}):
                fig.savefig(
                    target,
                    format=output_format,
                    metadata={"Date": None},
                )
        else:
            fig.savefig(target, format=output_format)
    finally:
        # Figure is not registered with pyplot, so clearing releases artists
        # without mutating or depending on pyplot's process-global registry.
        fig.clear()


def _fill_regions(ax, roof: RoofSpec, x_min: float, x_max: float, y_min: float) -> None:
    """Shade memory-bound and compute-bound regions under the roof."""
    ridge = roof.ridge_point
    n_pts = 256

    # memory-bound: x in [x_min, ridge], y from y_min up to bandwidth * x
    x_mem = np.logspace(math.log10(x_min), math.log10(ridge), n_pts)
    ax.fill_between(
        x_mem,
        y_min,
        roof.bandwidth * x_mem,
        color="#56B4E9",
        alpha=0.16,
        hatch="///",
        linewidth=0,
        label="memory-bound",
    )

    # compute-bound: x in [ridge, x_max], y from y_min up to compute ceiling
    x_cmp = np.logspace(math.log10(ridge), math.log10(x_max), n_pts)
    ax.fill_between(
        x_cmp,
        y_min,
        roof.compute,
        color="#E69F00",
        alpha=0.16,
        hatch="\\\\\\",
        linewidth=0,
        label="compute-bound",
    )


def _plot_roof(
    ax,
    roof: RoofSpec,
    x_values,
    *,
    dashed: bool,
    show_ridge_line: bool,
    y_min: float,
) -> None:
    y_values = np.minimum(roof.compute, roof.bandwidth * x_values)
    ax.plot(
        x_values,
        y_values,
        label=f"{roof.label} (ridge={_format_engineering(roof.ridge_point)} FLOP/Byte)",
        color=roof.color,
        linewidth=2.2,
        linestyle="--" if dashed else "-",
    )
    ax.scatter(
        [roof.ridge_point],
        [roof.compute],
        s=36,
        color=roof.color,
        edgecolor="white",
        linewidth=0.8,
        zorder=5,
    )
    if show_ridge_line:
        ax.plot(
            [roof.ridge_point, roof.ridge_point],
            [y_min, roof.compute],
            color=roof.color,
            linewidth=0.9,
            linestyle=":",
            alpha=0.7,
            zorder=2,
            label="_nolegend_",
        )


def _axis_bounds(request: PlotRequest) -> tuple[float, float, float, float]:
    x_candidates = [roof.ridge_point for roof in request.roofs]
    y_candidates = [roof.compute for roof in request.roofs]

    for operator in request.operators:
        x_candidates.append(operator.arithmetic_intensity)
        y_candidates.append(operator.compute)

    raw_x_min = min(x_candidates)
    raw_x_max = max(x_candidates)
    x_min = 10 ** math.floor(math.log10(raw_x_min) - 0.6)
    x_max = 10 ** math.ceil(math.log10(raw_x_max) + 0.6)

    for roof in request.roofs:
        y_candidates.append(min(roof.compute, roof.bandwidth * x_min))
        y_candidates.append(min(roof.compute, roof.bandwidth * x_max))

    raw_y_min = min(y_candidates)
    raw_y_max = max(y_candidates)
    y_min = raw_y_min / 1.35
    y_max = raw_y_max * 2.5
    return x_min, x_max, y_min, y_max


def _format_engineering(value: float) -> str:
    if value == 0:
        return "0"

    prefixes = {
        -18: "a",
        -15: "f",
        -12: "p",
        -9: "n",
        -6: "u",
        -3: "m",
        0: "",
        3: "K",
        6: "M",
        9: "G",
        12: "T",
        15: "P",
        18: "E",
    }
    exponent = int(math.floor(math.log10(abs(value)) / 3) * 3)
    exponent = max(min(exponent, 18), -18)
    scaled = value / (10**exponent)
    if abs(scaled - round(scaled)) < 1e-9:
        scaled_text = str(int(round(scaled)))
    else:
        scaled_text = f"{scaled:.2f}".rstrip("0").rstrip(".")
    return f"{scaled_text}{prefixes[exponent]}"
