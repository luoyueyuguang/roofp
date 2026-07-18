"""Validate the repository's root SKILL.md without external dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED_FIELDS = {"name", "description"}


def validate_skill(directory: str | Path) -> None:
    path = Path(directory) / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        closing_index = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("SKILL.md frontmatter is not closed") from exc

    metadata: dict[str, str] = {}
    for line in lines[1:closing_index]:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            raise ValueError(f"Invalid frontmatter line: {line!r}")
        key = key.strip()
        if key in metadata:
            raise ValueError(f"Duplicate frontmatter field: {key}")
        metadata[key] = value.strip()

    if set(metadata) != REQUIRED_FIELDS:
        raise ValueError("SKILL.md frontmatter must contain only name and description")
    name = metadata["name"]
    description = metadata["description"]
    if len(name) > 64 or not NAME_PATTERN.fullmatch(name):
        raise ValueError("Skill name must be <=64 lowercase letters, digits, or hyphens")
    if len(description) > 1024:
        raise ValueError("Skill description must not exceed 1024 characters")
    if "<" in description or ">" in description:
        raise ValueError("Skill description must not contain angle brackets")
    if not any(line.strip() for line in lines[closing_index + 1 :]):
        raise ValueError("SKILL.md must contain an instruction body")
    if len(lines) > 500:
        raise ValueError("SKILL.md should remain under 500 lines")


def main() -> None:
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    validate_skill(directory)
    print("SKILL.md is valid")


if __name__ == "__main__":
    main()
