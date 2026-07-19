import json
import re
import unittest
from pathlib import Path

from tests.validate_skill import validate_skill

ROOT = Path(__file__).resolve().parents[1]

SOURCE_TEST_PAIRS = {
    "roofp/model.py": ("tests/test_model.py",),
    "roofp/units.py": ("tests/test_units.py",),
    "roofp/plot.py": ("tests/test_plot.py",),
    "roofp/cli.py": ("tests/test_cli.py",),
    "roofp/mcp_server.py": ("tests/test_mcp_tools.py", "tests/test_mcp_protocol.py"),
}

REQUIRED_ROOF_METADATA = {
    "precision",
    "compute_kind",
    "bandwidth_level",
    "bandwidth_kind",
    "fma_flop_count",
    "sparsity",
}

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


def project_version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    if match is None:
        raise AssertionError("pyproject.toml is missing the project version")
    return match.group(1)


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

    def test_readme_install_does_not_launch_long_running_mcp_server(self) -> None:
        english = code_blocks(ROOT / "README.md")
        chinese = code_blocks(ROOT / "README_zh.md")
        self.assertNotIn("roofp-mcp", english[1][1])
        self.assertEqual(english[1], chinese[1])
        self.assertIn(
            "long-running stdio MCP server",
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "长驻的 stdio MCP Server",
            (ROOT / "README_zh.md").read_text(encoding="utf-8"),
        )

    def test_all_entry_documents_explain_distribution_and_usage_names(self) -> None:
        for filename in ("README.md", "README_zh.md", "AGENTS.md", "SKILL.md"):
            with self.subTest(filename=filename):
                text = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("pip install lyroofp", text)
                self.assertIn("import roofp", text)
                self.assertIn("roofp-mcp", text)

    def test_entry_documents_reference_current_release(self) -> None:
        version = project_version()
        for filename in ("README.md", "README_zh.md"):
            with self.subTest(filename=filename):
                text = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn(f"lyroofp {version}", text)
                self.assertIn(f"/releases/tag/v{version}", text)
                self.assertIn(f"/v{version}/SKILL.md", text)
        for filename in ("README.md", "README_zh.md", "AGENTS.md", "SKILL.md"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            for old_version in ("v0.2.0", "v0.2.1", "v0.2.2"):
                self.assertNotIn(old_version, text)

    def test_agents_source_map_uses_existing_paths_and_tests(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for source, tests in SOURCE_TEST_PAIRS.items():
            with self.subTest(source=source):
                self.assertTrue((ROOT / source).is_file())
                self.assertIn(f"`{source}`", agents)
                self.assertNotIn(f"`{Path(source).name}`", agents)
                for test in tests:
                    self.assertTrue((ROOT / test).is_file())
                    self.assertIn(f"`{test}`", agents)

    def test_skill_cold_start_paths_are_explicit_and_safe(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        bash_blocks = [
            body for language, body in code_blocks(ROOT / "SKILL.md") if language == "bash"
        ]
        install = bash_blocks[0]
        self.assertIn(f"pip install lyroofp=={project_version()}", install)
        self.assertNotIn("roofp-mcp", install)
        self.assertIn("long-running stdio MCP server", skill)
        self.assertIn("do not run it as a one-shot health check", skill)
        self.assertIn('"command": "roofp-mcp"', skill)
        self.assertIn("If the MCP tools are unavailable", skill)
        self.assertIn("The CLI does not expose peer-hardware", skill)
        self.assertIn("--output /tmp/roofp-analysis.json", skill)
        self.assertIn("--output /tmp/roofp-roofline.svg", skill)
        self.assertNotIn("--output analysis.json", skill)

    def test_skill_mcp_examples_supply_comparison_metadata(self) -> None:
        payloads = [
            json.loads(body)
            for language, body in code_blocks(ROOT / "SKILL.md")
            if language == "json"
        ]
        analyze = next(payload for payload in payloads if "roof" in payload)
        generate = next(payload for payload in payloads if "ideal" in payload)
        compare = next(payload for payload in payloads if "roofs" in payload)

        self.assertLessEqual(REQUIRED_ROOF_METADATA, set(analyze["roof"]))
        self.assertEqual(generate["ideal"]["compute_kind"], "theoretical")
        self.assertEqual(generate["actual"]["compute_kind"], "measured")
        self.assertEqual(generate["ideal"]["bandwidth_kind"], "theoretical")
        self.assertEqual(generate["actual"]["bandwidth_kind"], "measured")
        for roof in (generate["ideal"], generate["actual"], *compare["roofs"]):
            self.assertLessEqual(REQUIRED_ROOF_METADATA, set(roof))

    def test_ci_runs_repository_skill_validator(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python tests/validate_skill.py .", workflow)
        validate_skill(ROOT)


if __name__ == "__main__":
    unittest.main()
