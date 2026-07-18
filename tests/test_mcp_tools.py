import unittest

import anyio

from roofp.mcp_server import (
    HardwareMeasurement,
    OperatorInput,
    RoofInput,
    WorkloadInput,
    analyze_performance,
    compare_rooflines,
    generate_roofline,
    mcp,
)


def input_roof(label: str, compute="100 FLOP/s", bandwidth="10 B/s", **metadata):
    return RoofInput(label=label, compute=compute, bandwidth=bandwidth, **metadata)


class RooflineMcpToolTests(unittest.TestCase):
    def test_tool_schema_is_structured_and_ideal_is_required(self) -> None:
        tools = {tool.name: tool for tool in mcp._tool_manager.list_tools()}
        generate = tools["generate_roofline"]
        self.assertEqual(generate.parameters["required"], ["ideal"])
        self.assertIn("$defs", generate.parameters)
        self.assertNotIn("operators_json", generate.parameters["properties"])
        self.assertIsNotNone(generate.output_schema)
        self.assertIsNotNone(tools["compare_rooflines"].output_schema)

    def test_generate_defaults_are_directly_callable(self) -> None:
        result = generate_roofline(input_roof("Ideal"))
        self.assertEqual(result.schema_version, "2.0")
        self.assertEqual(result.analysis.operators, [])
        self.assertIsNone(result.svg)

    def test_generate_evaluates_ideal_and_actual_separately(self) -> None:
        result = generate_roofline(
            input_roof("Ideal", compute=100, bandwidth=10),
            [OperatorInput(name="Op", compute=40, arithmetic_intensity=5)],
            actual=input_roof("Measured", compute=50, bandwidth=20),
        )
        evaluations = result.analysis.operators[0]["evaluations"]
        self.assertEqual(set(evaluations), {"ideal", "actual"})
        self.assertEqual(evaluations["ideal"]["roof_ceiling_flop_per_second"], 50)
        self.assertEqual(evaluations["actual"]["roof_ceiling_flop_per_second"], 50)

    def test_analyze_returns_native_structured_result(self) -> None:
        result = analyze_performance(
            input_roof("Ideal"),
            [OperatorInput(name="Op", compute=50, arithmetic_intensity=10)],
        )
        self.assertEqual(result.schema_version, "2.0")
        evaluation = result.operators[0]["evaluations"]["ideal"]
        self.assertEqual(evaluation["utilization_ratio"], 0.5)

    def test_compare_theory_does_not_invent_utilization(self) -> None:
        result = compare_rooflines(
            [
                input_roof("Small", compute=100, bandwidth=100),
                input_roof("Large", compute=1000, bandwidth=1000),
            ],
            [WorkloadInput(name="Op", arithmetic_intensity=1)],
        )
        entry = result.comparison_matrix[0]
        self.assertEqual(entry["best_theoretical_hardware"], "Large")
        self.assertIsNone(entry["best_valid_utilization_hardware"])
        for hardware in entry["hardware"].values():
            self.assertIsNone(hardware["utilization_ratio"])

    def test_compare_uses_per_hardware_measurements(self) -> None:
        result = compare_rooflines(
            [
                input_roof("A", compute=100, bandwidth=10),
                input_roof("B", compute=200, bandwidth=20),
            ],
            [
                WorkloadInput(
                    name="Op",
                    arithmetic_intensity=20,
                    measurements=[
                        HardwareMeasurement(roof_label="A", compute=80),
                        HardwareMeasurement(roof_label="B", compute=100),
                    ],
                )
            ],
        )
        entry = result.comparison_matrix[0]
        self.assertEqual(entry["best_theoretical_hardware"], "B")
        self.assertEqual(entry["best_valid_utilization_hardware"], "A")
        self.assertEqual(entry["best_valid_utilization_ratio"], 0.8)

    def test_above_roof_measurement_is_excluded_from_ranking(self) -> None:
        result = compare_rooflines(
            [input_roof("A"), input_roof("B", compute=200, bandwidth=20)],
            [
                WorkloadInput(
                    name="Op",
                    arithmetic_intensity=20,
                    measurements=[
                        HardwareMeasurement(roof_label="A", compute=120),
                        HardwareMeasurement(roof_label="B", compute=100),
                    ],
                )
            ],
        )
        entry = result.comparison_matrix[0]
        self.assertEqual(entry["excluded_above_roof_measurements"], ["A"])
        self.assertEqual(entry["best_valid_utilization_hardware"], "B")

    def test_compare_reports_metadata_mismatch(self) -> None:
        result = compare_rooflines(
            [
                input_roof("A", precision="FP32", bandwidth_level="dram"),
                input_roof("B", precision="FP16", bandwidth_level="l2"),
            ]
        )
        self.assertTrue(any("precision" in item for item in result.metadata_warnings))
        self.assertTrue(any("bandwidth_level" in item for item in result.metadata_warnings))

    def test_compare_rejects_duplicate_and_unknown_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            compare_rooflines([input_roof("Same"), input_roof("Same")])
        with self.assertRaisesRegex(ValueError, "unknown roof"):
            compare_rooflines(
                [input_roof("A"), input_roof("B")],
                [
                    WorkloadInput(
                        name="Op",
                        arithmetic_intensity=1,
                        measurements=[HardwareMeasurement(roof_label="C", compute=1)],
                    )
                ],
            )

    def test_svg_is_opt_in_and_response_is_bounded(self) -> None:
        operators = [
            OperatorInput(name=f"op_{index}", compute=10, arithmetic_intensity=index + 1)
            for index in range(32)
        ]
        result = generate_roofline(input_roof("Ideal"), operators, include_svg=True)
        self.assertIsNotNone(result.svg)
        self.assertLess(len(result.svg), 300_000)
        too_many = operators + [
            OperatorInput(name=f"extra_{index}", compute=10, arithmetic_intensity=index + 40)
            for index in range(33)
        ]
        with self.assertRaisesRegex(ValueError, "at most 64"):
            generate_roofline(input_roof("Ideal"), too_many, include_svg=True)
        with self.assertRaisesRegex(ValueError, "at most 256"):
            generate_roofline(
                input_roof("Ideal"),
                [
                    OperatorInput(name=f"large_{index}", compute=1, arithmetic_intensity=1)
                    for index in range(257)
                ],
            )

    def test_framework_error_does_not_echo_large_raw_input(self) -> None:
        async def call_invalid():
            return await mcp.call_tool(
                "generate_roofline",
                {"ideal": {"label": "A", "compute": "x" * 100_001, "bandwidth": 1}},
            )

        with self.assertRaises(Exception) as raised:
            anyio.run(call_invalid)
        message = str(raised.exception)
        self.assertLess(len(message), 5_000)
        self.assertNotIn("x" * 10_000, message)

    def test_deep_legacy_json_string_fails_as_tool_error(self) -> None:
        nested = "[" * 1_100 + "]" * 1_100

        async def call_invalid():
            return await mcp.call_tool(
                "generate_roofline",
                {"ideal": {"label": "A", "compute": 1, "bandwidth": 1}, "operators": nested},
            )

        with self.assertRaises(Exception) as raised:
            anyio.run(call_invalid)
        self.assertLess(len(str(raised.exception)), 5_000)


if __name__ == "__main__":
    unittest.main()
