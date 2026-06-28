# roofp — Roofline Performance Analysis

Generate roofline plots and analyze compute/memory bottlenecks via MCP tools or CLI.

## When to use

- User asks about roofline analysis, arithmetic intensity, compute-bound vs memory-bound
- User wants to visualize operator performance against hardware limits
- User needs to compare performance across different hardware (e.g. H100 vs A100)
- User asks "is this kernel compute-bound or memory-bound?"
- Analyzing headroom, ridge ratio, bottleneck diagnosis

## MCP Tools

The roofp MCP server exposes three tools.

### `analyze_performance`

Quick analysis without plot generation. Returns JSON with bound type, headroom, ridge ratio, and natural-language descriptions.

```
ideal_compute: "1.2 TFLOP/s"
ideal_bandwidth: "800 GB/s"
operators_json: '[{"name":"GEMM","compute":"650 GFLOP/s","arithmetic_intensity":"650/200"}]'
```

Arithmetic intensity supports: `3.25`, `"3.25 FLOP/Byte"`, `"650/200"`, `"650 GFLOP/s / 200 GB/s"`.

Use this first for a quick bottleneck diagnosis before generating a plot.

### `generate_roofline`

Full analysis + SVG plot. Same parameters as `analyze_performance` plus optional actual roof and title.

```
ideal_compute: "1.2 TFLOP/s"
ideal_bandwidth: "800 GB/s"
actual_compute: "800 GFLOP/s"        # optional
actual_bandwidth: "500 GB/s"         # optional
operators_json: '[...]'
title: "My Roofline"
```

Returns `{"analysis": {...}, "svg": "<svg>...</svg>"}`.

### `compare_rooflines`

Compare operators across multiple hardware configs. Returns comparison matrix, best-hardware recommendation, and SVG overlay.

```
roofs_json: '[{"label":"H100","compute":"1.2 TFLOP/s","bandwidth":"800 GB/s"},{"label":"A100","compute":"312 TFLOP/s","bandwidth":"2 TB/s"}]'
operators_json: '[...]'
title: "Hardware Comparison"
```

Returns `{"comparison_matrix": [...], "summary": [...], "svg": "..."}`.

## Interpreting results

- **bound**: `"memory"` = limited by bandwidth (left of ridge), `"compute"` = limited by peak FLOP/s (right of ridge)
- **ridge_ratio**: arithmetic_intensity / ridge_point. >1 = compute-bound, <1 = memory-bound
- **headroom_ratio**: current performance / roofline ceiling. 1.0 = at the roof
- **description**: human-readable summary of the above

## CLI (non-MCP)

```bash
uv run python -m roofp --config examples/sample_config.json
uv run python -m roofp --silent --ideal-compute "1.2 TFLOP/s" --ideal-bandwidth "800 GB/s" --operator GEMM "650 GFLOP/s" "650/200" --output analysis.json
```

## Architecture

- `model.py` — data classes + `build_analysis()`
- `plot.py` — matplotlib rendering (SVG)
- `cli.py` — argparse CLI
- `units.py` — unit parsing (FLOP/s, Byte/s, FLOP/Byte)
- `mcp_server.py` — MCP stdio server
