<p align="center">
  <img src="docs/assets/logo.png" width="220" alt="roofp Logo">
</p>

<h1 align="center">roofp</h1>

<p align="center">
  <strong>Configurable roofline plotting for compute, bandwidth, and operator performance.</strong>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://opensource.org/license/mit/"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
  <a href="https://matplotlib.org/"><img src="https://img.shields.io/badge/Plotting-matplotlib-11557c" alt="matplotlib"></a>
</p>

This project generates roofline plots from either a JSON config file or
command-line arguments. It uses `matplotlib` for rendering and can write SVG,
PNG, PDF, or any other format supported by `matplotlib`.

## What the inputs mean

- `compute`: throughput in `FLOP/s`
- `bandwidth`: memory throughput in `Byte/s`
- `arithmetic intensity`: `compute / bandwidth`, in `FLOP/Byte`

For each roof, the tool builds:

- memory roof: `performance = bandwidth * arithmetic intensity`
- compute roof: `performance = peak FLOP/s`
- ridge point: `peak FLOP/s / bandwidth`

For each operator point, the tool accepts:

- `compute`: throughput in `FLOP/s`
- `arithmetic_intensity`: in `FLOP/Byte` — directly places the operator on the x-axis

The underlying bandwidth is derived as `compute / arithmetic_intensity`.

## Quick start

Install dependencies:

```bash
uv sync
```

Run with a JSON config:

```bash
uv run python -m roofp --config examples/sample_config.json
```

Run with command-line arguments only:

```bash
uv run python -m roofp \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --actual-compute "800 GFLOP/s" \
  --actual-bandwidth "500 GB/s" \
  --operator GEMM "650 GFLOP/s" "3.25 FLOP/Byte" \
  --operator Attention "280 GFLOP/s" "1.273 FLOP/Byte" \
  --output roofline.svg
```

Run with only ideal roof values:

```bash
uv run python -m roofp \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --output ideal_only.svg
```

### Silent mode (JSON analysis only)

`--silent` skips image generation and writes machine-readable JSON analysis to `--output`:

```bash
uv run python -m roofp --silent \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --operator GEMM "650 GFLOP/s" "3.25 FLOP/Byte" \
  --output analysis.json
```

The JSON includes per-operator analysis:

- `bound` — `"memory"` or `"compute"` relative to the ideal ridge point
- `ridge_ratio` — AI / ridge_point (>1 = compute-bound)
- `roof_performance_flops` — roofline ceiling at this AI
- `headroom_ratio` — current perf / roof perf

If both JSON config and CLI values are provided, CLI values override the same
fields from config.

## Supported units

Compute values are normalized to `FLOP/s`. Supported examples:

- `1e12`
- `1200 GFLOP/s`
- `1.2 TFLOP/s`
- `{"value": 1.2, "unit": "TFLOP/s"}`

Arithmetic intensity values are normalized to `FLOP/Byte`. Supported examples:

- `3.25`
- `3.25 FLOP/Byte`
- `{"value": 3.25, "unit": "FLOP/Byte"}`


Bandwidth values are normalized to `Byte/s`. Supported examples:

- `8e11`
- `800 GB/s`
- `745 GiB/s`
- `{"value": 800, "unit": "GB/s"}`

Plain numbers are accepted for backwards compatibility. They are interpreted as
already normalized values: `FLOP/s` for compute and `Byte/s` for bandwidth.

## JSON config format

```json
{
  "title": "Example Roofline",
  "output": "roofline.svg",
  "plot": {
    "width": 1280,
    "height": 720
  },
  "ideal": {
    "label": "Ideal roof",
    "compute": "1.2 TFLOP/s",
    "bandwidth": "800 GB/s"
  },
  "actual": {
    "label": "Measured roof",
    "compute": "800 GFLOP/s",
    "bandwidth": "500 GB/s"
  },
  "operators": [
    {
      "name": "GEMM",
      "compute": "650 GFLOP/s",
      "arithmetic_intensity": "3.25 FLOP/Byte"
    },
    {
      "name": "Attention",
      "compute": {
        "value": 280,
        "unit": "GFLOP/s"
      },
      "arithmetic_intensity": {
        "value": 1.273,
        "unit": "FLOP/Byte"
      }
    }
  ]
}
```

Notes:

- `ideal` is required.
- `actual` is optional.
- `operators` is optional and can be empty or contain many items.
- Each operator requires `compute` and `arithmetic_intensity`.
- All `compute`, `bandwidth`, and `arithmetic_intensity` values must be positive.

## Output

The output format is determined by the output filename suffix, for example
`roofline.svg`, `roofline.png`, or `roofline.pdf`.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```
