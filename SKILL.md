---
name: roofp
description: Analyze Roofline performance with structured MCP tools or the roofp CLI. Use when diagnosing compute-bound, memory-bound, or ridge-point workloads; measuring roof utilization and remaining headroom; comparing theoretical hardware ceilings separately from per-hardware measurements; checking Roofline metadata compatibility; or generating SVG, PNG, and PDF plots.
---

# roofp Roofline analysis

Use MCP tools for agent workflows. Use the CLI when the user needs a local SVG,
PNG, PDF, or JSON artifact.

## Install and invoke the correct names

Install the PyPI distribution as `lyroofp`, then use the stable `roofp` package
and command names:

```bash
python -m pip install lyroofp==0.2.3
roofp --version
```

Import the Python API with `import roofp`. Do not use `import lyroofp` and do
not invoke a `lyroofp` command; the distribution name is not an import or CLI
entry point.

In a repository checkout, prepare the locked environment before using
`--no-sync`:

```bash
uv sync --locked
uv run --no-sync roofp --version
```

## Choose an available execution path

Inspect the tools exposed by the current agent host before starting a process.

- If `analyze_performance`, `generate_roofline`, and `compare_rooflines` are
  available, call them directly. Do not launch another server.
- If the MCP tools are unavailable and the task is one-roof analysis, an
  ideal-versus-measured plot, or a local JSON artifact, use the CLI fallback below.
- If peer-hardware comparison or MCP integration is required, configure
  `roofp-mcp` as a long-running stdio MCP server in the client.

For a PyPI installation, use `roofp-mcp` as the client command:

```json
{
  "mcpServers": {
    "roofp": {
      "command": "roofp-mcp"
    }
  }
}
```

Client configuration formats vary. `roofp-mcp` intentionally waits for a client;
do not run it as a one-shot health check or wait for ordinary terminal output.

## Follow the workflow

1. Identify the compute precision, FLOP-counting convention, sparsity convention,
   bandwidth level, and whether each roof value is theoretical or measured.
2. Call `analyze_performance` for one-roof diagnosis without a plot.
3. Call `generate_roofline` for ideal-versus-measured analysis; set
   `include_svg: true` only when the SVG is needed.
4. Call `compare_rooflines` for two or more peer hardware roofs.
5. Explain theoretical capability separately from measured utilization.
6. Treat above-roof measurements as input-accounting warnings, not ranking winners.

Do not compare unqualified peak numbers from different precisions or bandwidth
levels as though they used the same convention. Surface `metadata_warnings` and
ask for missing conventions when they could change the conclusion.

## Supply structured MCP inputs

Pass arrays and objects directly. Do not encode them as JSON strings.

### Analyze one roof

Call `analyze_performance` with a `roof` and measured `operators`:

```json
{
  "roof": {
    "label": "System A FP32 theoretical",
    "compute": "1.2 TFLOP/s",
    "bandwidth": "800 GB/s",
    "precision": "FP32",
    "compute_kind": "theoretical",
    "bandwidth_level": "dram",
    "bandwidth_kind": "theoretical",
    "fma_flop_count": 2,
    "sparsity": "dense"
  },
  "operators": [
    {
      "name": "GEMM",
      "compute": "650 GFLOP/s",
      "arithmetic_intensity": "650 GFLOP/s/200 GB/s"
    }
  ]
}
```

### Analyze ideal and measured roofs

Call `generate_roofline` with required `ideal`, optional `actual`, optional
`operators`, and optional `title`:

```json
{
  "ideal": {
    "label": "FP32 theoretical",
    "compute": "1.2 TFLOP/s",
    "bandwidth": "800 GB/s",
    "precision": "FP32",
    "compute_kind": "theoretical",
    "bandwidth_level": "dram",
    "bandwidth_kind": "theoretical",
    "fma_flop_count": 2,
    "sparsity": "dense"
  },
  "actual": {
    "label": "FP32 measured",
    "compute": "800 GFLOP/s",
    "bandwidth": "500 GB/s",
    "precision": "FP32",
    "compute_kind": "measured",
    "bandwidth_level": "dram",
    "bandwidth_kind": "measured",
    "fma_flop_count": 2,
    "sparsity": "dense"
  },
  "operators": [
    {
      "name": "GEMM",
      "compute": "650 GFLOP/s",
      "arithmetic_intensity": "3.25 FLOP/Byte"
    }
  ],
  "include_svg": true
}
```

Leave `include_svg` false for compact results. SVG rendering supports at most 64
points; analysis without SVG supports at most 256 operators.

### Compare peer roofs

Call `compare_rooflines` with at least two uniquely labeled `roofs`. Supply a
workload's arithmetic intensity for theoretical comparison. Add one measurement
per roof only when those measurements actually exist:

```json
{
  "roofs": [
    {
      "label": "System A FP32",
      "compute": "1.2 TFLOP/s",
      "bandwidth": "800 GB/s",
      "precision": "FP32",
      "compute_kind": "theoretical",
      "fma_flop_count": 2,
      "bandwidth_level": "dram",
      "bandwidth_kind": "theoretical",
      "sparsity": "dense"
    },
    {
      "label": "System B FP32",
      "compute": "1.6 TFLOP/s",
      "bandwidth": "600 GB/s",
      "precision": "FP32",
      "compute_kind": "theoretical",
      "fma_flop_count": 2,
      "bandwidth_level": "dram",
      "bandwidth_kind": "theoretical",
      "sparsity": "dense"
    }
  ],
  "workloads": [
    {
      "name": "Kernel 1",
      "arithmetic_intensity": "2 FLOP/Byte",
      "measurements": [
        {"roof_label": "System A FP32", "compute": "700 GFLOP/s"},
        {"roof_label": "System B FP32", "compute": "850 GFLOP/s"}
      ]
    }
  ]
}
```

Read `best_theoretical_hardware` as the highest Roofline ceiling at the supplied
intensity. Read `best_valid_utilization_hardware` only as the valid measurement
using the greatest fraction of its own ceiling. Do not turn either value into a
complete hardware recommendation without workload coverage, latency, cost,
power, capacity, and software-support evidence.

## Interpret schema 2.0

- Read `bound` as `memory`, `compute`, or `ridge`.
- Read `ridge_ratio` as arithmetic intensity divided by the roof ridge point.
- Read `roof_ceiling_flop_per_second` as the attainable ceiling at that intensity.
- Read `utilization_ratio` as measured performance divided by that ceiling.
- Read `remaining_headroom_ratio` as `1 - utilization_ratio`.
- Read `above_roof: true` as a convention or measurement mismatch to investigate.
- Inspect every entry under `evaluations`; do not assume the ideal result also
  describes the actual or additional roofs.
- Expect `schema_version: "2.0"`; do not depend on removed 0.1 aliases such as
  `headroom_ratio`, `compute_flops`, or `roof_performance_flops`.

Arithmetic intensity accepts normalized numbers, `3.25 FLOP/Byte`, `650/200`,
and `650 GFLOP/s/200 GB/s`. Keep prefixes case-sensitive. Use uppercase `B` for
Byte. Reject bit rates when a Byte/s value is required.

## Create local artifacts

After installing from PyPI, call the CLI directly and write artifacts outside a
repository checkout:

```bash
roofp --analysis-only \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --operator GEMM "650 GFLOP/s" "650/200" \
  --output /tmp/roofp-analysis.json
roofp \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --operator GEMM "650 GFLOP/s" "650/200" \
  --output /tmp/roofp-roofline.svg
```

In a repository checkout, sync once and keep generated files out of the worktree:

```bash
uv sync --locked
uv run --no-sync roofp --config examples/sample_config.json \
  --output /tmp/roofp-roofline.svg
uv run --no-sync roofp --analysis-only \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --operator GEMM "650 GFLOP/s" "650/200" \
  --output /tmp/roofp-analysis.json
```

Parse stdout as JSON and read artifact status from stderr. Repeated `--operator`
arguments replace configured operators. The CLI does not expose peer-hardware
comparison; configure and call `compare_rooflines` instead of inventing a ranking.
