# AGENTS.md

Roofline plot generator (`roofp`) — development conventions.

## Architecture

- `model.py` — frozen dataclasses: `RoofSpec`, `OperatorPoint`, `PlotRequest`. Data + finite-positive validation. Also `build_analysis()` for machine-readable JSON output.
- `plot.py` — locked matplotlib rendering with guaranteed figure cleanup. Takes `PlotRequest`, writes SVG/PNG/PDF paths, and writes SVG to `BytesIO` for MCP.
- `cli.py` — argparse + JSON config merging. Delegates to `model`/`plot`. Supports `--silent` for JSON-only output.
- `mcp_server.py` — MCP stdio server exposing `analyze_performance`, `generate_roofline`, `compare_rooflines` tools. Comparison results distinguish highest ceiling from highest current utilization.
- `units.py` — parse human-readable `FLOP/s`, `Byte/s`, and `FLOP/Byte` strings into raw floats.

## Input conventions

- **Roofs**: `compute` (FLOP/s) + `bandwidth` (Byte/s). Ridge point = `compute / bandwidth`.
- **Operators**: `compute` (FLOP/s) + `arithmetic_intensity` (FLOP/Byte). Bandwidth is derived internally as `compute / arithmetic_intensity`.
- CLI `--operator` takes three positional args: `NAME COMPUTE ARITHMETIC_INTENSITY`.
- JSON config operators use `arithmetic_intensity` field (not `bandwidth`).

## Adding a plot feature

1. Define data/model in `model.py` if it carries new structured input.
2. Render in `plot.py`; keep helpers private (`_` prefix).
3. Wire CLI in `cli.py` if user-facing.
4. Regenerate example SVGs to smoke-test: `uv run python -m roofp --config examples/sample_config.json` (plus the two CLI-only examples in README).
5. Run tests: `uv run python -m unittest discover -s tests -v`.

## Plot rendering rules

- Axis: log-log, x = Arithmetic Intensity (FLOP/Byte), y = Attainable Performance (FLOP/s).
- Ideal roof = solid line, actual roof = dashed line. Ridge point marked with scatter.
- Operator points: scatter + offset annotation + drop lines to both axes + axis-edge labels.
- Region shading: translucent fill under the ideal roof, split at the ridge point into memory-bound (left) and compute-bound (right).
- Legend: lower right, framed.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```

## Git workflow

Periodically squash related commits to keep history clean.

**Squash last N commits:**
```bash
git reset --soft HEAD~N
git commit -m "concise summary"
```

**Squash specific commits via autosquash:**
```bash
git commit --fixup <target-sha>
git rebase -i --autosquash <base>
```
