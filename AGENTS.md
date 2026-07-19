# AGENTS.md

Develop and release the Roofline analysis project using the conventions below.

## Start from the repository root

- Require Python 3.10 or newer and use `uv` with the committed `uv.lock`.
- Keep implementation code under `roofp/`, tests under `tests/`, and example input
  under `examples/`.
- Inspect `pyproject.toml`, the affected implementation file, and its paired test
  before editing.

Prepare the development environment and confirm the installed entry point:

```bash
uv sync --locked --all-groups
uv run --no-sync roofp --version
```

## Keep package identities distinct

- Install the PyPI distribution with `python -m pip install lyroofp`.
- Import the Python package with `import roofp`.
- Run the CLI as `roofp` and the MCP server as `roofp-mcp`.
- Do not document or implement `import lyroofp` or a `lyroofp` command; neither is
  a public interface.

## Locate implementation and tests

| Area | Implementation | Primary tests | Preserve |
|---|---|---|---|
| Data model and schema | `roofp/model.py` | `tests/test_model.py` | Frozen validated dataclasses, tolerance-aware classification, schema `2.0` |
| Unit parsing | `roofp/units.py` | `tests/test_units.py` | Case-sensitive FLOP/s, Byte/s, and FLOP/Byte semantics |
| Plotting | `roofp/plot.py` | `tests/test_plot.py` | Isolated figures, render lock, peer-roof semantics, cleanup |
| CLI and JSON config | `roofp/cli.py` | `tests/test_cli.py` | Strict config, stdout JSON, stderr status, atomic artifacts |
| MCP tools | `roofp/mcp_server.py` | `tests/test_mcp_tools.py`, `tests/test_mcp_protocol.py` | Strict structured I/O, bounded payloads, theory/measurement separation |
| Packaging and entry points | `pyproject.toml`, `MANIFEST.in`, `roofp/__init__.py` | `tests/test_packaging.py`, `tests/verify_distribution.py` | Distribution `lyroofp`; import and commands under `roofp` |
| Human and agent docs | `README.md`, `README_zh.md`, `AGENTS.md`, `SKILL.md` | `tests/test_docs.py`, `tests/validate_skill.py` | Paired READMEs and executable cold-start guidance |

Prefer `--analysis-only` for JSON artifacts; retain `--silent` only as a
compatibility alias. `roofp-mcp` is a long-running stdio server, not a one-shot
health-check command.

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

## Change only affected interfaces

1. Update models and validation first when structured data or semantics change.
2. Update CLI/config behavior only when the user-facing command path is affected.
3. Update structured MCP models, descriptions, and outputs only when the MCP path
   is affected.
4. Update plotting only when the data relationship needs visualization.
5. Update every affected document when public commands, schemas, examples,
   package identity, MCP behavior, release metadata, or contributor workflow changes.
6. Whenever either README changes, keep English/Chinese heading order, code
   examples, and link targets paired.
7. Regenerate `roofline.svg` and `ideal_only.svg` after plot/config changes.
8. When changing the distribution version or name, update `pyproject.toml`,
   `roofp/__init__.py`, `uv.lock`, version assertions, release links,
   `tests/verify_distribution.py`, and CI together.

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
