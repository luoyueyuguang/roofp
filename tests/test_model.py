import math
import unittest
from dataclasses import FrozenInstanceError

from roofp.model import (
    RELATIVE_TOLERANCE,
    OperatorPoint,
    PlotRequest,
    RoofSpec,
    build_analysis,
    classify_bound,
    comparison_metadata_warnings,
    evaluate_operator,
)


def make_roof(label: str = "Ideal", **overrides) -> RoofSpec:
    values = {"compute": 120.0, "bandwidth": 30.0, "color": "#0072B2"}
    values.update(overrides)
    return RoofSpec(label=label, **values)


class RooflineModelTests(unittest.TestCase):
    def test_ridge_point_and_derived_operator_bandwidth(self) -> None:
        self.assertEqual(make_roof().ridge_point, 4.0)
        operator = OperatorPoint(name="Conv", compute=90.0, arithmetic_intensity=6.0)
        self.assertEqual(operator.bandwidth, 15.0)

    def test_bound_classification_uses_relative_tolerance(self) -> None:
        ridge = 4.0
        self.assertEqual(classify_bound(ridge, ridge), "ridge")
        self.assertEqual(
            classify_bound(ridge * (1.0 + RELATIVE_TOLERANCE / 2), ridge),
            "ridge",
        )
        self.assertEqual(classify_bound(3.0, ridge), "memory")
        self.assertEqual(classify_bound(5.0, ridge), "compute")

    def test_evaluation_reports_memory_compute_and_roof_tolerance(self) -> None:
        roof = make_roof(compute=100.0, bandwidth=10.0)
        memory = evaluate_operator(
            roof,
            OperatorPoint(name="memory", compute=25.0, arithmetic_intensity=5.0),
        )
        self.assertEqual(memory.bound, "memory")
        self.assertEqual(memory.roof_ceiling_flop_per_second, 50.0)
        self.assertEqual(memory.utilization_ratio, 0.5)
        compute = evaluate_operator(
            roof,
            OperatorPoint(name="compute", compute=80.0, arithmetic_intensity=20.0),
        )
        self.assertEqual(compute.bound, "compute")
        self.assertAlmostEqual(compute.remaining_headroom_ratio, 0.2)
        near_roof = evaluate_operator(
            roof,
            OperatorPoint(
                name="near",
                compute=100.0 * (1.0 + RELATIVE_TOLERANCE / 2),
                arithmetic_intensity=20.0,
            ),
        )
        self.assertFalse(near_roof.above_roof)
        self.assertEqual(near_roof.remaining_headroom_ratio, 0.0)

    def test_above_roof_is_diagnostic(self) -> None:
        request = PlotRequest(
            title="test",
            ideal=make_roof(compute=100.0, bandwidth=10.0),
            operators=(OperatorPoint(name="Impossible", compute=120.0, arithmetic_intensity=20.0),),
        )
        operator = build_analysis(request)["operators"][0]
        evaluation = operator["evaluations"]["ideal"]
        self.assertTrue(evaluation["above_roof"])
        self.assertLess(evaluation["remaining_headroom_ratio"], 0)
        self.assertIn("Verify peak values", operator["description"])

    def test_analysis_has_dimensional_schema_and_every_roof_evaluation(self) -> None:
        request = PlotRequest(
            title="test",
            ideal=make_roof("Ideal"),
            actual=make_roof("Measured", compute=100.0, bandwidth=20.0),
            additional_roofs=(make_roof("Peer", compute=90.0, bandwidth=45.0),),
            operators=(OperatorPoint(name="Op", compute=60.0, arithmetic_intensity=3.0),),
        )
        result = build_analysis(request)
        self.assertEqual(result["schema_version"], "2.0")
        self.assertEqual(set(result["roofs"]), {"ideal", "actual", "additional_0"})
        self.assertEqual(
            set(result["operators"][0]["evaluations"]),
            {"ideal", "actual", "additional_0"},
        )
        self.assertEqual(
            result["roofs"]["ideal"]["peak_compute_flop_per_second"],
            120.0,
        )
        self.assertNotIn("compute_flops", result["roofs"]["ideal"])
        self.assertIn("achieved_bandwidth_byte_per_second", result["operators"][0])

    def test_plot_request_converts_collections_to_immutable_tuples(self) -> None:
        source = [OperatorPoint(name="Op", compute=1.0, arithmetic_intensity=1.0)]
        request = PlotRequest(title="test", ideal=make_roof(), operators=source)
        source.append(OperatorPoint(name="Later", compute=1.0, arithmetic_intensity=1.0))
        self.assertIsInstance(request.operators, tuple)
        self.assertEqual(len(request.operators), 1)
        with self.assertRaises(FrozenInstanceError):
            request.title = "changed"

    def test_metadata_is_preserved_and_mismatches_are_reported(self) -> None:
        first = make_roof(
            "A",
            precision="FP32",
            compute_kind="theoretical",
            bandwidth_level="dram",
            fma_flop_count=2,
            sparsity="dense",
        )
        second = make_roof(
            "B",
            precision="FP16",
            compute_kind="measured",
            bandwidth_level="l2",
            fma_flop_count=1,
        )
        warnings = comparison_metadata_warnings((first, second))
        self.assertTrue(any("precision" in warning for warning in warnings))
        self.assertTrue(any("bandwidth_level" in warning for warning in warnings))
        self.assertTrue(any("fma_flop_count" in warning for warning in warnings))
        self.assertTrue(any("omit sparsity" in warning for warning in warnings))

    def test_model_rejects_non_finite_boolean_and_invalid_metadata(self) -> None:
        for value in (math.nan, math.inf, -math.inf, True, 0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_roof(compute=value)
        with self.assertRaisesRegex(ValueError, "fma_flop_count"):
            make_roof(fma_flop_count=4)
        with self.assertRaisesRegex(ValueError, "fma_flop_count"):
            make_roof(fma_flop_count=True)
        with self.assertRaisesRegex(ValueError, "compute_kind"):
            make_roof(compute_kind="estimated")

    def test_request_validates_types_and_pixel_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "operators"):
            PlotRequest(title="test", ideal=make_roof(), operators=("invalid",))
        with self.assertRaisesRegex(ValueError, "pixels"):
            PlotRequest(title="test", ideal=make_roof(), width=16_000, height=16_000)
        with self.assertRaisesRegex(ValueError, "peer_roofs"):
            PlotRequest(title="test", ideal=make_roof(), peer_roofs="yes")


if __name__ == "__main__":
    unittest.main()
