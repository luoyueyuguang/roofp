import json
import tempfile
import unittest
from pathlib import Path

from roofp.cli import build_parser, load_request_from_args
from roofp.model import OperatorPoint, RoofSpec
from roofp.plot import _axis_bounds
from roofp.units import parse_arithmetic_intensity, parse_bandwidth, parse_compute


class RooflineModelTests(unittest.TestCase):
    def test_roof_ridge_point(self) -> None:
        roof = RoofSpec(label="Ideal roof", compute=120.0, bandwidth=30.0, color="#000000")
        self.assertEqual(roof.ridge_point, 4.0)

    def test_operator_arithmetic_intensity(self) -> None:
        operator = OperatorPoint(name="Conv", compute=90.0, bandwidth=15.0)
        self.assertEqual(operator.arithmetic_intensity, 6.0)

    def test_build_analysis_memory_bound(self) -> None:
        from roofp.model import PlotRequest, build_analysis
        request = PlotRequest(
            title="test",
            ideal=RoofSpec(label="Ideal", compute=120.0, bandwidth=30.0, color="#000"),
            operators=[OperatorPoint(name="MemOp", compute=60.0, bandwidth=20.0, color="#111")],
        )
        result = build_analysis(request)
        self.assertEqual(result["operators"][0]["bound"], "memory")
        self.assertAlmostEqual(result["operators"][0]["ridge_ratio"], 0.75, places=4)
        self.assertAlmostEqual(result["operators"][0]["headroom_ratio"], 2.0 / 3.0, places=4)

    def test_build_analysis_compute_bound(self) -> None:
        from roofp.model import PlotRequest, build_analysis
        request = PlotRequest(
            title="test",
            ideal=RoofSpec(label="Ideal", compute=100.0, bandwidth=10.0, color="#000"),
            operators=[OperatorPoint(name="CmpOp", compute=80.0, bandwidth=4.0, color="#222")],
        )
        result = build_analysis(request)
        self.assertEqual(result["operators"][0]["bound"], "compute")
        self.assertGreater(result["operators"][0]["ridge_ratio"], 1.0)

    def test_build_analysis_memory_bound_low_ai(self) -> None:
        from roofp.model import PlotRequest, build_analysis
        request = PlotRequest(
            title="test",
            ideal=RoofSpec(label="Ideal", compute=100.0, bandwidth=50.0, color="#000"),
            operators=[OperatorPoint(name="MemOp", compute=30.0, bandwidth=30.0, color="#333")],
        )
        result = build_analysis(request)
        self.assertEqual(result["operators"][0]["bound"], "memory")
        self.assertLess(result["operators"][0]["ridge_ratio"], 1.0)

    def test_build_analysis_no_operators(self) -> None:
        from roofp.model import PlotRequest, build_analysis
        request = PlotRequest(
            title="test",
            ideal=RoofSpec(label="Ideal", compute=100.0, bandwidth=10.0, color="#000"),
        )
        result = build_analysis(request)
        self.assertEqual(result["operators"], [])
        self.assertNotIn("actual", result["roofs"])

    def test_build_analysis_with_actual(self) -> None:
        from roofp.model import PlotRequest, build_analysis
        request = PlotRequest(
            title="test",
            ideal=RoofSpec(label="Ideal", compute=120.0, bandwidth=30.0, color="#000"),
            actual=RoofSpec(label="Measured", compute=100.0, bandwidth=20.0, color="#111"),
        )
        result = build_analysis(request)
        self.assertIn("actual", result["roofs"])
        self.assertEqual(result["roofs"]["actual"]["compute_flops"], 100.0)
        self.assertEqual(result["roofs"]["actual"]["ridge_point_flop_per_byte"], 5.0)


class UnitParsingTests(unittest.TestCase):
    def test_compute_units(self) -> None:
        self.assertEqual(parse_compute("1 TFLOP/s"), 1e12)
        self.assertEqual(parse_compute({"value": 800, "unit": "GFLOP/s"}), 8e11)
        self.assertEqual(parse_compute(120.0), 120.0)

    def test_bandwidth_units(self) -> None:
        self.assertEqual(parse_bandwidth("800 GB/s"), 8e11)
        self.assertEqual(parse_bandwidth({"value": 1, "unit": "GiB/s"}), 1024.0**3)
        self.assertEqual(parse_bandwidth(30.0), 30.0)

    def test_arithmetic_intensity_plain(self) -> None:
        self.assertEqual(parse_arithmetic_intensity(3.25), 3.25)

    def test_arithmetic_intensity_unit(self) -> None:
        self.assertEqual(parse_arithmetic_intensity("3.25 FLOP/Byte"), 3.25)
        self.assertEqual(parse_arithmetic_intensity("1.5 FLOPS/BYTE"), 1.5)

    def test_arithmetic_intensity_bare_ratio(self) -> None:
        self.assertEqual(parse_arithmetic_intensity("650/200"), 3.25)
        self.assertEqual(parse_arithmetic_intensity("90/15"), 6.0)

    def test_arithmetic_intensity_ratio_with_units(self) -> None:
        self.assertEqual(parse_arithmetic_intensity("650 GFLOP/s / 200 GB/s"), 3.25)
        self.assertEqual(parse_arithmetic_intensity("1.2 TFLOP/s / 800 GB/s"), 1.5)

    def test_arithmetic_intensity_dict(self) -> None:
        self.assertEqual(parse_arithmetic_intensity({"value": 3.25, "unit": "FLOP/Byte"}), 3.25)

    def test_arithmetic_intensity_invalid(self) -> None:
        with self.assertRaises(ValueError):
            parse_arithmetic_intensity("not a number")
        with self.assertRaises(ValueError):
            parse_arithmetic_intensity("3.25 unknown/unit")


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
                "6 FLOP/Byte",
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
            "operators": [{"name": "Conv", "compute": "90 FLOP/s", "arithmetic_intensity": "6 FLOP/Byte"}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            parser = build_parser()
            args = parser.parse_args(["--config", str(config_path)])
            request, _ = load_request_from_args(args)
            self.assertEqual(request.title, "Config Roofline")
            self.assertEqual(len(request.operators), 1)



    def test_operator_with_bare_ratio(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--ideal-compute", "120 FLOP/s",
                "--ideal-bandwidth", "30 B/s",
                "--operator", "Conv", "90 FLOP/s", "90/15",
            ]
        )
        request, _ = load_request_from_args(args)
        self.assertAlmostEqual(request.operators[0].arithmetic_intensity, 6.0, places=4)

    def test_operator_with_ratio_units(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--ideal-compute", "1.2 TFLOP/s",
                "--ideal-bandwidth", "800 GB/s",
                "--operator", "GEMM", "650 GFLOP/s", "650 GFLOP/s / 200 GB/s",
            ]
        )
        request, _ = load_request_from_args(args)
        self.assertAlmostEqual(request.operators[0].arithmetic_intensity, 3.25, places=4)

    def test_silent_flag_accepted(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--silent",
                "--ideal-compute", "120 FLOP/s",
                "--ideal-bandwidth", "30 B/s",
            ]
        )
        self.assertTrue(args.silent)

    def test_operator_with_dict_arithmetic_intensity(self) -> None:
        config = {
            "ideal": {"compute": "120 FLOP/s", "bandwidth": "30 B/s"},
            "operators": [
                {
                    "name": "Conv",
                    "compute": "90 FLOP/s",
                    "arithmetic_intensity": {"value": 6.0, "unit": "FLOP/Byte"},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            parser = build_parser()
            args = parser.parse_args(["--config", str(config_path)])
            request, _ = load_request_from_args(args)
            self.assertAlmostEqual(request.operators[0].arithmetic_intensity, 6.0, places=4)

    def test_multiple_operators_with_mixed_ai_formats(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--ideal-compute", "120 FLOP/s",
                "--ideal-bandwidth", "30 B/s",
                "--operator", "Op1", "90 FLOP/s", "90/15",
                "--operator", "Op2", "60 FLOP/s", "60 GFLOP/s / 30 GB/s",
            ]
        )
        request, _ = load_request_from_args(args)
        self.assertEqual(len(request.operators), 2)
        self.assertAlmostEqual(request.operators[0].arithmetic_intensity, 6.0, places=4)
        self.assertAlmostEqual(request.operators[1].arithmetic_intensity, 2.0, places=4)
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
                    "3.25 FLOP/Byte",
                ]
            )
        )
        _, _, _, y_max = _axis_bounds(request)
        self.assertLessEqual(y_max / request.ideal.compute, 2.5)


if __name__ == "__main__":
    unittest.main()
