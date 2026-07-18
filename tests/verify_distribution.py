"""Verify built wheel and sdist contents in the release CI job."""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path


def main(directory: str = "dist") -> None:
    dist = Path(directory)
    wheels = list(dist.glob("roofp-0.2.0-*.whl"))
    sdists = list(dist.glob("roofp-0.2.0.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("Expected exactly one roofp 0.2.0 wheel and sdist")

    with zipfile.ZipFile(wheels[0]) as archive:
        wheel_names = set(archive.namelist())
    required_modules = {
        "roofp/__init__.py",
        "roofp/cli.py",
        "roofp/mcp_server.py",
        "roofp/model.py",
        "roofp/plot.py",
        "roofp/units.py",
    }
    missing_modules = required_modules - wheel_names
    if missing_modules:
        raise SystemExit(f"Wheel is missing modules: {sorted(missing_modules)}")

    with tarfile.open(sdists[0], "r:gz") as archive:
        sdist_names = {Path(name).as_posix() for name in archive.getnames()}
    suffixes = {
        "README_zh.md",
        "SKILL.md",
        "examples/sample_config.json",
        "docs/assets/logo.png",
    }
    for suffix in suffixes:
        if not any(name.endswith(suffix) for name in sdist_names):
            raise SystemExit(f"sdist is missing {suffix}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dist")
