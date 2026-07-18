import math
import unittest

from roofp.units import parse_arithmetic_intensity, parse_bandwidth, parse_compute


class UnitParsingTests(unittest.TestCase):
    def test_compute_decimal_prefixes_are_case_sensitive(self) -> None:
        self.assertEqual(parse_compute("1 MFLOP/s"), 1e6)
        self.assertEqual(parse_compute("1 GFLOPS"), 1e9)
        with self.assertRaisesRegex(ValueError, "uppercase M"):
            parse_compute("1 mFLOP/s")

    def test_bare_flop_is_not_throughput(self) -> None:
        with self.assertRaisesRegex(ValueError, "operation count"):
            parse_compute("10 FLOP")

    def test_compute_accepts_number_string_and_mapping(self) -> None:
        self.assertEqual(parse_compute(120.0), 120.0)
        self.assertEqual(parse_compute("1 TFLOP/s"), 1e12)
        self.assertEqual(parse_compute({"value": 800, "unit": "GFLOP/s"}), 8e11)

    def test_bandwidth_preserves_decimal_and_binary_meaning(self) -> None:
        self.assertEqual(parse_bandwidth("1 GB/s"), 1e9)
        self.assertEqual(parse_bandwidth("1 GiB/s"), 1024.0**3)
        self.assertEqual(parse_bandwidth({"value": 800, "unit": "GB/s"}), 8e11)

    def test_bandwidth_rejects_bits_and_ambiguous_milli(self) -> None:
        for value in ("1 Gbps", "1 Gb/s", "1 bps"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Bit-rate"):
                parse_bandwidth(value)
        with self.assertRaisesRegex(ValueError, "uppercase M"):
            parse_bandwidth("1 mB/s")

    def test_arithmetic_intensity_direct_forms(self) -> None:
        self.assertEqual(parse_arithmetic_intensity(3.25), 3.25)
        self.assertEqual(parse_arithmetic_intensity("3.25 FLOP/Byte"), 3.25)
        self.assertEqual(
            parse_arithmetic_intensity({"value": 3.25, "unit": "FLOP/Byte"}),
            3.25,
        )

    def test_arithmetic_intensity_ratio_forms(self) -> None:
        self.assertEqual(parse_arithmetic_intensity("650/200"), 3.25)
        self.assertEqual(
            parse_arithmetic_intensity("650 GFLOP/s / 200 GB/s"),
            3.25,
        )
        self.assertEqual(parse_arithmetic_intensity("650 GFLOP/s/200 GB/s"), 3.25)

    def test_per_is_replaced_only_as_a_token(self) -> None:
        self.assertEqual(parse_compute("1 GFLOP per s"), 1e9)
        with self.assertRaises(ValueError):
            parse_compute("1 hyperFLOP/s")

    def test_mapping_unit_must_be_a_string(self) -> None:
        with self.assertRaisesRegex(ValueError, "unit must be a string"):
            parse_bandwidth({"value": 1, "unit": 2})

    def test_parsers_reject_non_finite_zero_negative_and_boolean(self) -> None:
        for parser in (parse_compute, parse_bandwidth, parse_arithmetic_intensity):
            for value in (math.nan, math.inf, -math.inf, 0, -1, True):
                with (
                    self.subTest(parser=parser.__name__, value=value),
                    self.assertRaises(ValueError),
                ):
                    parser(value)

    def test_invalid_ratio_does_not_leak_zero_division(self) -> None:
        for value in ("1/0", "1 FLOP/s / 0 B/s", "not a number"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_arithmetic_intensity(value)


if __name__ == "__main__":
    unittest.main()
