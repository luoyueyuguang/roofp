import re
import unittest
from pathlib import Path

from tests.validate_skill import validate_skill

ROOT = Path(__file__).resolve().parents[1]

HEADING_PAIRS = [
    ("## Roofline model", "## Roofline 模型"),
    ("## Install and run", "## 安装与运行"),
    ("### Analysis-only mode", "### 仅分析模式"),
    ("## Supported units", "## 支持的单位"),
    ("## JSON configuration", "## JSON 配置"),
    ("## Analysis schema 2.0", "## 分析 schema 2.0"),
    ("## MCP server", "## MCP Server"),
    ("### `analyze_performance`", "### `analyze_performance`"),
    ("### `generate_roofline`", "### `generate_roofline`"),
    ("### `compare_rooflines`", "### `compare_rooflines`"),
    ("## Release and integrity", "## 发布与完整性校验"),
    ("## AI agent Skill", "## AI Agent Skill"),
    ("## Tests and release checks", "## 测试与发布校验"),
    ("## License", "## 许可证"),
]


def markdown_headings(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(("## ", "### "))
    ]


def code_blocks(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    return [
        (language, body.strip())
        for language, body in re.findall(r"```([^\n]*)\n(.*?)```", text, re.DOTALL)
    ]


def link_targets(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"\[[^]]+\]\(([^)]+)\)", text)


class DocumentationTests(unittest.TestCase):
    def test_readme_headings_have_one_to_one_translation(self) -> None:
        english = markdown_headings(ROOT / "README.md")
        chinese = markdown_headings(ROOT / "README_zh.md")
        self.assertEqual(english, [pair[0] for pair in HEADING_PAIRS])
        self.assertEqual(chinese, [pair[1] for pair in HEADING_PAIRS])

    def test_readme_code_examples_are_paired(self) -> None:
        english = code_blocks(ROOT / "README.md")
        chinese = code_blocks(ROOT / "README_zh.md")
        self.assertEqual(len(english), 17)
        self.assertEqual(len(chinese), len(english))
        self.assertEqual(english[0][0], "text")
        self.assertEqual(chinese[0][0], "text")
        self.assertEqual(english[1:], chinese[1:])

    def test_readme_link_targets_are_paired(self) -> None:
        self.assertEqual(
            link_targets(ROOT / "README.md"),
            link_targets(ROOT / "README_zh.md"),
        )

    def test_all_entry_documents_explain_distribution_and_usage_names(self) -> None:
        for filename in ("README.md", "README_zh.md", "AGENTS.md", "SKILL.md"):
            with self.subTest(filename=filename):
                text = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("pip install lyroofp", text)
                self.assertIn("import roofp", text)
                self.assertIn("roofp-mcp", text)

    def test_entry_documents_reference_current_release(self) -> None:
        for filename in ("README.md", "README_zh.md"):
            with self.subTest(filename=filename):
                text = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("lyroofp 0.2.2", text)
                self.assertIn("/releases/tag/v0.2.2", text)
                self.assertIn("/v0.2.2/SKILL.md", text)
        for filename in ("README.md", "README_zh.md", "AGENTS.md", "SKILL.md"):
            self.assertNotIn(
                "v0.2.0",
                (ROOT / filename).read_text(encoding="utf-8"),
            )

    def test_ci_runs_repository_skill_validator(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python tests/validate_skill.py .", workflow)
        validate_skill(ROOT)


if __name__ == "__main__":
    unittest.main()
