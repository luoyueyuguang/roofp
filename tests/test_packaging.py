import importlib.metadata
import json
import unittest
from pathlib import Path

import roofp

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_runtime_and_distribution_versions_match(self) -> None:
        self.assertEqual(roofp.__version__, "0.2.2")
        self.assertEqual(importlib.metadata.version("lyroofp"), roofp.__version__)

    def test_distribution_name_is_distinct_from_import_name(self) -> None:
        metadata = importlib.metadata.metadata("lyroofp")
        self.assertEqual(metadata["Name"], "lyroofp")
        self.assertEqual(roofp.__name__, "roofp")

    def test_console_entry_points_exist(self) -> None:
        names = {entry.name for entry in importlib.metadata.entry_points(group="console_scripts")}
        self.assertTrue({"roofp", "roofp-mcp"}.issubset(names))

    def test_manifest_includes_human_and_agent_assets(self) -> None:
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        for path in (
            "README_zh.md",
            "SKILL.md",
            "examples/sample_config.json",
            "docs/assets/logo.png",
            "tests/validate_skill.py",
        ):
            self.assertIn(path, manifest)

    def test_readme_uses_pinned_hardened_skill_download(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("pip install lyroofp", readme)
        self.assertIn("/v0.2.2/SKILL.md", readme)
        self.assertIn("curl --fail --silent --show-error --location", readme)
        self.assertNotIn("/main/SKILL.md\n", readme)

    def test_sample_config_is_valid_json_with_measurement_metadata(self) -> None:
        sample = json.loads((ROOT / "examples/sample_config.json").read_text())
        self.assertEqual(sample["ideal"]["precision"], sample["actual"]["precision"])
        self.assertEqual(sample["ideal"]["fma_flop_count"], 2)
        self.assertEqual(sample["ideal"]["bandwidth_level"], "dram")


if __name__ == "__main__":
    unittest.main()
