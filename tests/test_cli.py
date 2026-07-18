import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from roofp.cli import (
    _atomic_write_plot,
    build_parser,
    load_request_from_args,
    main,
)


class RooflineCliTests(unittest.TestCase):
    def parse(self, *arguments: str):
        return build_parser().parse_args(list(arguments))

    def test_cli_request_and_compatibility_alias(self) -> None:
        args = self.parse(
            "--silent",
            "--ideal-compute",
            "120 FLOP/s",
            "--ideal-bandwidth",
            "30 B/s",
            "--operator",
            "Conv",
            "90 FLOP/s",
            "6 FLOP/Byte",
        )
        request, output = load_request_from_args(args)
        self.assertTrue(args.analysis_only)
        self.assertEqual(output, "analysis.json")
        self.assertEqual(request.ideal.ridge_point, 4.0)
        self.assertEqual(request.operators[0].arithmetic_intensity, 6.0)

    def test_analysis_only_does_not_reuse_svg_config_output(self) -> None:
        config = {
            "output": "roofline.svg",
            "ideal": {"compute": "120 FLOP/s", "bandwidth": "30 B/s"},
        }
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            _, output = load_request_from_args(
                self.parse("--config", str(config_path), "--analysis-only")
            )
        self.assertEqual(output, "analysis.json")

    def test_analysis_only_rejects_explicit_non_json_output(self) -> None:
        with self.assertRaisesRegex(ValueError, r"\.json"):
            load_request_from_args(
                self.parse(
                    "--analysis-only",
                    "--ideal-compute",
                    "1 FLOP/s",
                    "--ideal-bandwidth",
                    "1 B/s",
                    "--output",
                    "wrong.svg",
                )
            )

    def test_config_is_strict_and_metadata_is_loaded(self) -> None:
        config = {
            "ideal": {
                "compute": 120,
                "bandwidth": 30,
                "precision": "FP32",
                "fma_flop_count": 2,
                "unknown": True,
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown ideal"):
                load_request_from_args(self.parse("--config", str(path)))
            del config["ideal"]["unknown"]
            path.write_text(json.dumps(config), encoding="utf-8")
            request, _ = load_request_from_args(self.parse("--config", str(path)))
        self.assertEqual(request.ideal.precision, "FP32")
        self.assertEqual(request.ideal.fma_flop_count, 2)

    def test_cli_operators_replace_config_operators(self) -> None:
        config = {
            "ideal": {"compute": 120, "bandwidth": 30},
            "operators": [{"name": "Configured", "compute": 10, "arithmetic_intensity": 1}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            request, _ = load_request_from_args(
                self.parse(
                    "--config",
                    str(path),
                    "--operator",
                    "CLI",
                    "20 FLOP/s",
                    "2 FLOP/Byte",
                )
            )
        self.assertEqual([operator.name for operator in request.operators], ["CLI"])

    def test_main_stdout_is_json_and_status_is_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = main(
                    [
                        "--analysis-only",
                        "--ideal-compute",
                        "120 FLOP/s",
                        "--ideal-bandwidth",
                        "30 B/s",
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue())["schema_version"], "2.0")
            self.assertEqual(json.loads(output.read_text())["schema_version"], "2.0")
            self.assertNotIn("Wrote", stdout.getvalue())
            self.assertIn("Wrote analysis", stderr.getvalue())

    def test_plot_status_is_stderr_and_stdout_remains_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plot.svg"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = main(
                    [
                        "--ideal-compute",
                        "120 FLOP/s",
                        "--ideal-bandwidth",
                        "30 B/s",
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(result, 0)
            json.loads(stdout.getvalue())
            self.assertTrue(output.read_bytes().startswith(b"<?xml"))
            self.assertIn("Wrote roofline", stderr.getvalue())

    def test_atomic_plot_preserves_existing_file_on_render_failure(self) -> None:
        request, _ = load_request_from_args(
            self.parse(
                "--ideal-compute",
                "120 FLOP/s",
                "--ideal-bandwidth",
                "30 B/s",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plot.svg"
            output.write_text("original", encoding="utf-8")

            def fail(_request, temporary_path):
                Path(temporary_path).write_text("partial", encoding="utf-8")
                raise OSError("render failed")

            with self.assertRaisesRegex(OSError, "render failed"):
                _atomic_write_plot(request, output, fail)
            self.assertEqual(output.read_text(encoding="utf-8"), "original")
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_main_validation_error_has_no_traceback(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_analysis_file_replacement_uses_os_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            with (
                mock.patch("roofp.cli.os.replace", wraps=os.replace) as replace,
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                main(
                    [
                        "--analysis-only",
                        "--ideal-compute",
                        "1 FLOP/s",
                        "--ideal-bandwidth",
                        "1 B/s",
                        "--output",
                        str(output),
                    ]
                )
            replace.assert_called_once()


if __name__ == "__main__":
    unittest.main()
