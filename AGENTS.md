# AGENTS.md

Develop and release the Roofline analysis project using the conventions below.

## Keep package identities distinct

- Install the PyPI distribution with `python -m pip install lyroofp`.
- Import the Python package with `import roofp`.
- Run the CLI as `roofp` and the MCP server as `roofp-mcp`.
- Do not document or implement `import lyroofp` or a `lyroofp` command; neither is
  a public interface.

## Understand the architecture

- `model.py` defines frozen `RoofSpec`, `OperatorPoint`, `RoofEvaluation`, and
  `PlotRequest` dataclasses, finite-positive validation, metadata compatibility,
  tolerance-aware classification, and schema-versioned `build_analysis()` output.
- `units.py` parses case-sensitive `FLOP/s`, `Byte/s`, and `FLOP/Byte` values.
- `plot.py` renders SVG/PNG/PDF with an isolated Matplotlib `Figure`, a render lock,
  peer-roof semantics, optional bound shading, and guaranteed cleanup.
- `cli.py` merges strict JSON configuration with CLI overrides. Prefer
  `--analysis-only` for JSON artifacts; retain `--silent` only as a compatibility
  alias. Write JSON to stdout, status to stderr, and artifacts atomically.
- `mcp_server.py` exposes structured `analyze_performance`, `generate_roofline`,
  and `compare_rooflines` tools. Keep Pydantic inputs strict, outputs structured,
  SVG opt-in, payload sizes bounded, and theory separate from measurements.

## Preserve input and analysis conventions

- Define roofs with `compute` in FLOP/s and `bandwidth` in Byte/s. Compute the
  ridge point as `compute / bandwidth`.
- Define operators with measured `compute` in FLOP/s and
  `arithmetic_intensity` in FLOP/Byte. Derive achieved bandwidth as
  `compute / arithmetic_intensity`.
- Keep precision, compute kind, bandwidth level/kind, FMA counting, and sparsity
  metadata explicit when comparing hardware.
- Treat above-roof measurements as accounting warnings and exclude them from
  valid utilization rankings.
- Keep analysis schema `2.0` dimensional names unambiguous. Do not restore the
  removed `compute_flops`, `roof_performance_flops`, or `headroom_ratio` aliases.

## Preserve plot semantics

- Use log-log axes: arithmetic intensity on x and attainable FLOP/s on y.
- For one hardware target, draw the ideal roof solid, the measured roof dashed,
  and shade ideal memory/compute regions when requested.
- For peer hardware comparison, draw every peer with equal line style, show each
  ridge independently, and do not shade the first peer's bound regions across
  the whole comparison.
- Keep SVG text as text, use supported `.svg`, `.png`, or `.pdf` suffixes, and
  avoid registering figures in global `pyplot` state.

## Make changes through every interface

1. Update models and validation.
2. Update CLI and strict JSON config handling when user-facing.
3. Update structured MCP models, descriptions, and output schemas.
4. Update plotting only when the data relationship needs visualization.
5. Update `README.md`, `README_zh.md`, `AGENTS.md`, and `SKILL.md` together.
6. Keep English and Chinese README heading order and code examples paired.
7. Regenerate `roofline.svg` and `ideal_only.svg` after plot/config changes.
8. Update version assertions, `tests/verify_distribution.py`, CI, and `uv.lock`
   when changing the distribution version or name.

## Validate before committing or publishing

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

Build from the final tagged commit. Publish to TestPyPI first, install the exact
version in a clean environment, and run import/CLI/MCP/plot smoke checks before
publishing the identical files to PyPI. Attach those exact files, `SKILL.md`, and
`SHA256SUMS` to the matching GitHub Release.
