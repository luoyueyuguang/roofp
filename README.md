[English](https://github.com/luoyueyuguang/roofp/blob/main/README.md) · [中文](https://github.com/luoyueyuguang/roofp/blob/main/README_zh.md)

<p align="center">
  <img src="https://raw.githubusercontent.com/luoyueyuguang/roofp/main/docs/assets/logo.png" width="220" alt="roofp logo">
</p>

<h1 align="center">roofp</h1>

<p align="center">
  <strong>Schema-versioned Roofline analysis, comparison, and plotting for humans and AI agents.</strong>
</p>

roofp accepts JSON configuration, CLI arguments, or structured MCP calls. It
generates SVG, PNG, and PDF plots and reports every measured operator against
each configured roof. Version 0.2 separates theoretical hardware capability
from per-hardware measured utilization and makes dimensional units explicit in
the output schema.

## Roofline model

For a roof with peak compute `P` in `FLOP/s`, bandwidth `B` in `Byte/s`, and
arithmetic intensity `I` in `FLOP/Byte`:

```text
ridge point = P / B
roof ceiling(I) = min(P, B * I)
utilization = measured performance / roof ceiling(I)
```

An operator left of the ridge is memory-bound, one right of it is
compute-bound, and a value equal within the documented numerical tolerance is
reported as `ridge`. A measurement above its configured roof is diagnostic
evidence of mismatched units, precision, FLOP counting, sparsity conventions,
or measurement scope—not a valid utilization winner.

## Install and run

The current release is `lyroofp 0.2.3` on
[PyPI](https://pypi.org/project/lyroofp/) and
[GitHub Releases](https://github.com/luoyueyuguang/roofp/releases/tag/v0.2.3).
Install the distribution as `lyroofp`, then import and invoke it as `roofp`:

```bash
python -m pip install lyroofp==0.2.3
roofp --version
```

```python
import roofp

print(roofp.__version__)
```

There is no public `lyroofp` command or `import lyroofp` package. `lyroofp` is
only the package-index distribution name; the stable Python and command
interfaces are `roofp` and `roofp-mcp`.

`roofp-mcp` is a long-running stdio MCP server command, not a one-shot health
check. Configure or start it only when an MCP client will connect.

Development checkout:

```bash
uv sync --locked --all-groups
uv run --no-sync roofp --config examples/sample_config.json
```

CLI-only example:

```bash
uv run --no-sync roofp \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --actual-compute "800 GFLOP/s" \
  --actual-bandwidth "500 GB/s" \
  --operator GEMM "650 GFLOP/s" "3.25 FLOP/Byte" \
  --output roofline.svg
```

The CLI writes exactly one JSON document to stdout. Human-readable artifact
status goes to stderr, so shell tools can safely consume stdout:

```bash
uv run --no-sync roofp --config examples/sample_config.json > result.json
```

### Analysis-only mode

`--analysis-only` skips plotting and atomically writes a JSON artifact.
`--silent` remains an alias for compatibility:

```bash
uv run --no-sync roofp --analysis-only \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --operator GEMM "650 GFLOP/s" "3.25 FLOP/Byte" \
  --output analysis.json
```

When a plot-oriented config selects `roofline.svg`, adding `--analysis-only`
uses `analysis.json` unless the CLI explicitly provides another `.json` path.
This prevents JSON from being written into an image-named file.

## Supported units

Inputs may be normalized numbers, strings, or `{ "value": ..., "unit": ... }`
objects in JSON configuration.

| Quantity | Normalized unit | Examples |
|---|---|---|
| Compute throughput | `FLOP/s` | `1e12`, `1200 GFLOP/s`, `1.2 TFLOP/s` |
| Bandwidth | `Byte/s` | `8e11`, `800 GB/s`, `745 GiB/s` |
| Arithmetic intensity | `FLOP/Byte` | `3.25`, `3.25 FLOP/Byte`, `650 GFLOP/s/200 GB/s` |

Prefixes are case-sensitive: `M` means mega. Ambiguous lowercase `m` is
rejected. Uppercase `B` means bytes; bit-rate forms such as `Gb/s` and `Gbps`
are rejected rather than silently interpreted as Byte/s. Bare `FLOP` is an
operation count, not throughput, and is rejected; common throughput spellings
such as `GFLOPS` remain supported.

## JSON configuration

See the complete [sample configuration](https://github.com/luoyueyuguang/roofp/blob/main/examples/sample_config.json).

```json
{
  "title": "Example Roofline",
  "output": "roofline.svg",
  "plot": {
    "width": 1280,
    "height": 720,
    "show_bound_regions": true
  },
  "ideal": {
    "label": "FP32 theoretical roof",
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
    "label": "FP32 measured roof",
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
  ]
}
```

The config schema is strict: misspelled or unknown fields fail early. `ideal`
is required, `actual` is optional, and every roof must provide compute and
bandwidth together. All numeric quantities must be finite and positive. When
one or more `--operator` options are supplied, they replace the configured
operator list rather than appending to it.

## Analysis schema 2.0

All analysis results include `"schema_version": "2.0"`. Dimensional names are
explicit, including:

- `peak_compute_flop_per_second`
- `bandwidth_byte_per_second`
- `measured_performance_flop_per_second`
- `achieved_bandwidth_byte_per_second`
- `arithmetic_intensity_flop_per_byte`
- `roof_ceiling_flop_per_second`

Each operator contains an `evaluations` object with separate `ideal`, `actual`,
and `additional_N` results. An evaluation includes `bound`, `ridge_ratio`,
`utilization_ratio`, `remaining_headroom_ratio`, and `above_roof`. Version 0.2
intentionally removes ambiguous 0.1 aliases such as `headroom_ratio` and
`compute_flops`.

## MCP server

After installing from PyPI, start the MCP server directly:

```bash
roofp-mcp
```

The command intentionally remains running while it waits for or serves an MCP
client; it does not print a version and exit.

For development, prepare the locked environment and disable implicit syncing
when starting the long-running server:

```bash
uv sync --locked
uv run --no-sync roofp-mcp
```

For a PyPI installation, use `roofp-mcp` directly as the client's stdio command.
For a repository checkout, use this configuration after the one-time sync:

```json
{
  "mcpServers": {
    "roofp": {
      "command": "uv",
      "args": [
        "run",
        "--no-sync",
        "--directory",
        "/absolute/path/to/roofp",
        "roofp-mcp"
      ]
    }
  }
}
```

The server exposes structured inputs and structured outputs—do not JSON-encode
lists inside strings.

### `analyze_performance`

Use one roof and measured operators for diagnosis:

```json
{
  "roof": {
    "label": "FP32 theoretical",
    "compute": "1.2 TFLOP/s",
    "bandwidth": "800 GB/s",
    "precision": "FP32"
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

### `generate_roofline`

Accepts a required `ideal` roof, optional `actual` roof, and optional operators.
Set `include_svg: true` to include the SVG. It defaults to false so ordinary
agent calls remain compact; SVG calls support at most 64 plotted points.

### `compare_rooflines`

This tool accepts peer `roofs` and workloads. Theoretical comparison needs only
arithmetic intensity. Put measured performance under the matching roof label
when a per-hardware utilization comparison is actually available:

```json
{
  "roofs": [
    {
      "label": "System A FP32",
      "compute": "1.2 TFLOP/s",
      "bandwidth": "800 GB/s",
      "precision": "FP32",
      "fma_flop_count": 2,
      "bandwidth_level": "dram"
    },
    {
      "label": "System B FP32",
      "compute": "1.6 TFLOP/s",
      "bandwidth": "600 GB/s",
      "precision": "FP32",
      "fma_flop_count": 2,
      "bandwidth_level": "dram"
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

`best_theoretical_hardware` ranks capability. `best_valid_utilization_hardware`
is emitted only from valid per-hardware measurements. Above-roof measurements
are preserved in `excluded_above_roof_measurements` but cannot win. Metadata
warnings flag mismatched or partially omitted precision, bandwidth level, FMA
count, and sparsity conventions.

## Release and integrity

Release `v0.2.3` contains the same wheel and sdist published to PyPI, the
standalone `SKILL.md`, and `SHA256SUMS` covering all three files:

- [GitHub Release v0.2.3](https://github.com/luoyueyuguang/roofp/releases/tag/v0.2.3)
- [PyPI lyroofp](https://pypi.org/project/lyroofp/)
- [TestPyPI lyroofp](https://test.pypi.org/project/lyroofp/)

Verify downloaded release files from the directory that contains them:

```bash
sha256sum -c SHA256SUMS
```

## AI agent Skill

The repository [SKILL.md](https://github.com/luoyueyuguang/roofp/blob/main/SKILL.md)
describes the 0.2 MCP workflow. Install a version-pinned copy for Codex:

```bash
mkdir -p ~/.codex/skills/roofp
curl --fail --silent --show-error --location --proto '=https' \
  --output ~/.codex/skills/roofp/SKILL.md \
  https://raw.githubusercontent.com/luoyueyuguang/roofp/v0.2.3/SKILL.md
```

For another agent, place the same pinned file at that product's documented
skill location. Review the downloaded instructions before enabling them. To
verify only the Skill against the checksum attached to the same release:

```bash
curl --fail --silent --show-error --location --proto '=https' \
  --output SHA256SUMS \
  https://github.com/luoyueyuguang/roofp/releases/download/v0.2.3/SHA256SUMS
grep ' SKILL.md$' SHA256SUMS | sha256sum -c -
```

## Tests and release checks

```bash
uv sync --locked --all-groups
uv run --no-sync python -W error -m unittest discover -s tests -v
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy roofp
uv run --no-sync python tests/validate_skill.py .
uv run --no-sync coverage run -m unittest discover -s tests
uv run --no-sync coverage report
uv run --no-sync python -m compileall -q roofp tests
uv lock --check --offline
uv pip check
uv build
python tests/verify_distribution.py dist
```

CI covers Python 3.10–3.14, lowest direct dependencies, protocol behavior,
wheel-only installation, linting, type checks, coverage, source distribution,
and Skill validation.

## License

MIT. See [LICENSE](https://github.com/luoyueyuguang/roofp/blob/main/LICENSE).
