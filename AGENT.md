# AGENT.md

Roofline plot generator (`roofp`) — development conventions.

## Architecture

- `model.py` — frozen dataclasses: `RoofSpec`, `OperatorPoint`, `PlotRequest`. No logic beyond validation.
- `plot.py` — pure matplotlib rendering. Stateless, takes `PlotRequest`, writes file.
- `cli.py` — argparse + JSON config merging. Delegates to `model`/`plot`.
- `units.py` — parse human-readable compute/bandwidth strings into raw FLOP/s and Byte/s.

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
