import json
import tempfile
import unittest
from pathlib import Path

from roofp.cli import build_parser, load_request_from_args
from roofp.model import OperatorPoint, RoofSpec
from roofp.plot import _axis_bounds
from roofp.units import parse_bandwidth, parse_compute


class RooflineModelTests(unittest.TestCase):
    def test_roof_ridge_point(self) -> None:
        roof = RoofSpec(label="Ideal roof", compute=120.0, bandwidth=30.0, color="#000000")
        self.assertEqual(roof.ridge_point, 4.0)

    def test_operator_arithmetic_intensity(self) -> None:
        operator = OperatorPoint(name="Conv", compute=90.0, bandwidth=15.0)
        self.assertEqual(operator.arithmetic_intensity, 6.0)


class UnitParsingTests(unittest.TestCase):
    def test_compute_units(self) -> None:
        self.assertEqual(parse_compute("1 TFLOP/s"), 1e12)
        self.assertEqual(parse_compute({"value": 800, "unit": "GFLOP/s"}), 8e11)
        self.assertEqual(parse_compute(120.0), 120.0)

    def test_bandwidth_units(self) -> None:
        self.assertEqual(parse_bandwidth("800 GB/s"), 8e11)
        self.assertEqual(parse_bandwidth({"value": 1, "unit": "GiB/s"}), 1024.0**3)
        self.assertEqual(parse_bandwidth(30.0), 30.0)


class RooflineCliTests(unittest.TestCase):
    def test_cli_only_request(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--ideal-compute",
                "120 FLOP/s",
                "--ideal-bandwidth",
                "30 B/s",
                "--actual-compute",
                "100 FLOP/s",
                "--actual-bandwidth",
                "20 B/s",
                "--operator",
                "Conv",
                "90 FLOP/s",
                "15 B/s",
            ]
        )
        request, output = load_request_from_args(args)
        self.assertEqual(request.ideal.ridge_point, 4.0)
        self.assertEqual(request.actual.ridge_point, 5.0)
        self.assertEqual(request.operators[0].arithmetic_intensity, 6.0)
        self.assertEqual(output, "roofline.svg")

    def test_operators_are_optional(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--ideal-compute",
                "1 TFLOP/s",
                "--ideal-bandwidth",
                "500 GB/s",
            ]
        )
        request, _ = load_request_from_args(args)
        self.assertEqual(request.ideal.ridge_point, 2.0)
        self.assertEqual(request.operators, [])

    def test_config_request(self) -> None:
        config = {
            "title": "Config Roofline",
            "ideal": {"compute": "120 FLOP/s", "bandwidth": "30 B/s"},
            "operators": [{"name": "Conv", "compute": "90 FLOP/s", "bandwidth": "15 B/s"}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            parser = build_parser()
            args = parser.parse_args(["--config", str(config_path)])
            request, _ = load_request_from_args(args)
            self.assertEqual(request.title, "Config Roofline")
            self.assertEqual(len(request.operators), 1)


class RooflinePlotTests(unittest.TestCase):
    def test_plot_request_can_be_built_without_operator_points(self) -> None:
        request, _ = load_request_from_args(
            build_parser().parse_args(
                [
                    "--ideal-compute",
                    "120 FLOP/s",
                    "--ideal-bandwidth",
                    "30 B/s",
                ]
            )
        )
        self.assertEqual(request.operators, [])
        self.assertEqual(request.ideal.ridge_point, 4.0)

    def test_axis_bounds_keep_roof_close_to_top(self) -> None:
        request, _ = load_request_from_args(
            build_parser().parse_args(
                [
                    "--ideal-compute",
                    "1.2 TFLOP/s",
                    "--ideal-bandwidth",
                    "800 GB/s",
                    "--actual-compute",
                    "800 GFLOP/s",
                    "--actual-bandwidth",
                    "500 GB/s",
                    "--operator",
                    "GEMM",
                    "650 GFLOP/s",
                    "200 GB/s",
                ]
            )
        )
        _, _, _, y_max = _axis_bounds(request)
        self.assertLessEqual(y_max / request.ideal.compute, 2.5)


if __name__ == "__main__":
    unittest.main()
