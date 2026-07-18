import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from roofp.model import OperatorPoint, PlotRequest, RoofSpec
from roofp.plot import _axis_bounds, write_plot


def roof(label: str, compute: float = 100.0, bandwidth: float = 10.0, color="#0072B2"):
    return RoofSpec(label=label, compute=compute, bandwidth=bandwidth, color=color)


class RooflinePlotTests(unittest.TestCase):
    def test_output_format_is_inferred_from_suffix(self) -> None:
        request = PlotRequest(title="formats", ideal=roof("Ideal"))
        signatures = {
            "svg": b"<?xml",
            "png": b"\x89PNG\r\n\x1a\n",
            "pdf": b"%PDF",
        }
        with tempfile.TemporaryDirectory() as directory:
            for suffix, signature in signatures.items():
                with self.subTest(suffix=suffix):
                    output = Path(directory) / f"roofline.{suffix}"
                    write_plot(request, str(output))
                    self.assertTrue(output.read_bytes().startswith(signature))

    def test_bytes_buffer_uses_svg(self) -> None:
        output = io.BytesIO()
        write_plot(PlotRequest(title="buffer", ideal=roof("Ideal")), output)
        self.assertTrue(output.getvalue().startswith(b"<?xml"))

    def test_peer_comparison_has_no_single_roof_bound_fill(self) -> None:
        request = PlotRequest(
            title="peers",
            ideal=roof("A"),
            additional_roofs=(roof("B", compute=200, bandwidth=5, color="#D55E00"),),
            peer_roofs=True,
            show_bound_regions=True,
        )
        buffer = io.BytesIO()
        with mock.patch("roofp.plot._fill_regions") as fill:
            write_plot(request, buffer)
        fill.assert_not_called()
        svg = buffer.getvalue().decode("utf-8")
        self.assertIn("A", svg)
        self.assertIn("B", svg)
        self.assertNotIn("memory-bound", svg)

    def test_peer_roofs_use_equal_line_style(self) -> None:
        request = PlotRequest(
            title="peers",
            ideal=roof("A"),
            additional_roofs=(roof("B", color="#D55E00"),),
            peer_roofs=True,
            show_bound_regions=False,
        )
        seen: list[bool] = []
        from roofp import plot

        original = plot._plot_roof

        def capture(*args, **kwargs):
            seen.append(kwargs["dashed"])
            return original(*args, **kwargs)

        with mock.patch("roofp.plot._plot_roof", side_effect=capture):
            write_plot(request, io.BytesIO())
        self.assertEqual(seen, [False, False])

    def test_single_hardware_distinguishes_actual_roof(self) -> None:
        request = PlotRequest(
            title="actual",
            ideal=roof("Ideal"),
            actual=roof("Measured", compute=80, bandwidth=8, color="#D55E00"),
            show_bound_regions=False,
        )
        seen: list[bool] = []
        from roofp import plot

        original = plot._plot_roof

        def capture(*args, **kwargs):
            seen.append(kwargs["dashed"])
            return original(*args, **kwargs)

        with mock.patch("roofp.plot._plot_roof", side_effect=capture):
            write_plot(request, io.BytesIO())
        self.assertEqual(seen, [False, True])

    def test_axis_bounds_include_operator_and_roofs(self) -> None:
        request = PlotRequest(
            title="bounds",
            ideal=roof("Ideal"),
            operators=(OperatorPoint(name="Op", compute=1_000, arithmetic_intensity=100),),
        )
        x_min, x_max, y_min, y_max = _axis_bounds(request)
        self.assertLess(x_min, request.ideal.ridge_point)
        self.assertGreater(x_max, 100)
        self.assertLess(y_min, 100)
        self.assertGreater(y_max, 1_000)

    def test_unsupported_format_and_invalid_color_fail_cleanly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported output format"):
            write_plot(PlotRequest(title="test", ideal=roof("Ideal")), "plot.invalid")
        invalid = roof("Invalid", color="not-a-color")
        with self.assertRaises(ValueError):
            write_plot(PlotRequest(title="test", ideal=invalid), io.BytesIO())


if __name__ == "__main__":
    unittest.main()
